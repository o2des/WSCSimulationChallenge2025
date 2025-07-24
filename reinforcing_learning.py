import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import matplotlib.pyplot as plt
import os
import csv
import traceback # Import traceback for debugging

# Check if CUDA is available for GPU acceleration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# CHANGES: Enhanced Actor-Critic network with dynamic architecture support
class ActorCritic(nn.Module):
    """
    Actor-Critic network for multi-agent reinforcement learning.
    
    CHANGES:
    - Dynamic actor network initialization
    - Enhanced state dimension caching
    - Improved error handling and validation
    """
    def __init__(self, state_dim, action_space_func):
        super(ActorCritic, self).__init__()
        self.action_space_func = action_space_func
        self.state_dim_cache = state_dim # Cache state_dim for potential actor initialization
        
        # Common feature extraction layers
        self.common = nn.Sequential(
            nn.Linear(state_dim, 128),  # Ensure state_dim matches the state length
            nn.ReLU()
        )
        
        # CHANGES: Dynamic actor network (initialized when needed)
        self.actors = None  # Dynamically defined based on action space
        
        # Critic network for value estimation
        self.critic = nn.Linear(128, 1)

    def _ensure_actors_initialized(self, agent_idx, example_state_for_size=None):
        """
        Ensure self.actors is initialized for model loading and inference.
        
        CHANGES: Enhanced initialization with better error handling
        
        Args:
            agent_idx: Index of the agent
            example_state_for_size: Example state for determining action space size
        """
        if self.actors is None:
            # Create virtual state if no example provided
            if example_state_for_size is None:
                example_state_for_size = torch.zeros(self.state_dim_cache).to(device)
                if example_state_for_size.dim() == 1: # forward expects batch
                    example_state_for_size = example_state_for_size.unsqueeze(0)

            # Determine action space size
            action_space_size = self.action_space_func(example_state_for_size, agent_idx)
            if action_space_size <= 0: # Add validation
                raise ValueError(f"Agent {agent_idx}: action_space_size must be positive, got {action_space_size}. Check action_space_funcs.")

            # Initialize actor network
            self.actors = nn.Sequential(
                nn.Linear(128, action_space_size),
                nn.Softmax(dim=-1)
            ).to(device)

    def forward(self, state, agent_idx):
        """
        Forward pass through the Actor-Critic network.
        
        CHANGES: Enhanced input validation and dynamic actor creation
        
        Args:
            state: Input state tensor
            agent_idx: Index of the agent
            
        Returns:
            Tuple of (action_probabilities, state_value)
        """
        # Ensure state is a tensor and on the correct device
        if not isinstance(state, torch.Tensor):
            state_tensor = torch.tensor(state, dtype=torch.float32).to(device)
        else:
            state_tensor = state.to(device, dtype=torch.float32)

        if state_tensor.dim() == 1: # If it's a single sample, add batch dimension
            state_tensor = state_tensor.unsqueeze(0)

        # Extract common features
        features = self.common(state_tensor)
        action_space_size = self.action_space_func(state_tensor, agent_idx)

        # Dynamically create/validate Actor network
        if (
            self.actors is None
            or not isinstance(self.actors[-1], nn.Linear)  # Ensure the last layer is Linear (before Softmax)
            or self.actors[-1].out_features != action_space_size
        ):
            self.actors = nn.Sequential(
                nn.Linear(128, action_space_size),
                nn.Softmax(dim=-1)
            ).to(device)

        action_probs = self.actors(features)
        state_value = self.critic(features)

        # If the original input is a single sample, remove batch dimension
        if state.dim() == 1:
            action_probs = action_probs.squeeze(0)
            state_value = state_value.squeeze(0)

        return action_probs, state_value

# CHANGES: Enhanced MAPPO algorithm with hyperparameter tuning and evaluation mode
class MAPPO:
    """
    Multi-Agent Proximal Policy Optimization (MAPPO) algorithm.
    
    CHANGES:
    - Configurable hyperparameters (lr, gamma, clip_param)
    - Evaluation mode support
    - Enhanced model loading/saving
    - Improved metrics tracking and visualization
    """
    def __init__(self, state_dims, action_space_funcs, num_agents, lr=1e-3, gamma=0.99, clip_param=0.2,
                 load_from_folder_path=None):
        """
        Initialize MAPPO algorithm.
        
        CHANGES: Added hyperparameter configuration
        
        Args:
            state_dims: List of state dimensions for each agent
            action_space_funcs: List of action space functions for each agent
            num_agents: Number of agents
            lr: Learning rate (CHANGES: configurable)
            gamma: Discount factor (CHANGES: configurable)
            clip_param: PPO clipping parameter (CHANGES: configurable)
            load_from_folder_path: Path to load pre-trained models
        """
        self.num_agents = num_agents
        self.gamma = gamma
        self.clip_param = clip_param
        self.action_space_funcs = action_space_funcs
        self.state_dims_cache = state_dims

        # Initialize agents and optimizers
        self.agents = [
            ActorCritic(state_dims[i], self.action_space_funcs[i]).to(device) for i in range(num_agents)
        ]
        self.optimizers = [optim.Adam(agent.parameters(), lr=lr) for agent in self.agents]
        
        # Training data storage
        self.trajectories = [[] for _ in range(num_agents)]
        self.cumulative_rewards = [[] for _ in range(num_agents)]
        self.update_counts = [0 for _ in range(num_agents)]
        
        # CHANGES: Enhanced metrics tracking
        self.policy_entropy = [[] for _ in range(num_agents)]
        self.value_losses = [[] for _ in range(num_agents)]
        self.gradient_norms = [[] for _ in range(num_agents)]

        # File management
        self.current_results_folder = "."
        self.gradient_csv_file_basename = "gradient_norms.csv"

        # CHANGES: Evaluation mode support
        self.is_eval_mode = False

        # Load pre-trained models if specified
        if load_from_folder_path:
            self.current_results_folder = load_from_folder_path
            gradient_csv_full_path = os.path.join(load_from_folder_path, self.gradient_csv_file_basename)
            if not os.path.exists(gradient_csv_full_path):
                 with open(gradient_csv_full_path, mode='w', newline='') as file:
                    writer = csv.writer(file)
                    header = ["Update Step"] + [f"Agent {i} Gradient Norm" for i in range(num_agents)]
                    writer.writerow(header)
        
        if load_from_folder_path is not None:
            print(f"Attempting to load model parameters from CSV files in: {load_from_folder_path}")
            self.load_from_csv(load_from_folder_path)

    # CHANGES: Added evaluation mode functionality
    def set_eval_mode(self, eval_mode_on=True):
        """
        Set the agent to evaluation mode (no learning/updates) or training mode.
        
        CHANGES: New functionality for model evaluation
        
        Args:
            eval_mode_on: Boolean flag to enable/disable evaluation mode
        """
        self.is_eval_mode = eval_mode_on
        if self.is_eval_mode:
            print("MAPPO agent set to EVALUATION mode. Policy updates will be skipped.")
            # PyTorch's eval() mode for nn.Module affects layers like Dropout, BatchNorm
            for agent_model in self.agents:
                agent_model.eval()
        else:
            print("MAPPO agent set to TRAINING mode. Policy updates will be performed.")
            for agent_model in self.agents:
                agent_model.train()

    def select_action(self, action_state, env_state, agent_idx):
        """
        Select action using the current policy.
        
        CHANGES: Enhanced action selection with evaluation mode support
        
        Args:
            action_state: Available actions state
            env_state: Environmental state
            agent_idx: Index of the agent
            
        Returns:
            Tuple of (selected_action, action_probability)
        """
        state = action_state + env_state
        if not isinstance(state, (list, np.ndarray)) or len(np.shape(state)) != 1:
            raise ValueError(f"Invalid state format: {state}. State must be a flat list or 1D array.")
        state_tensor = torch.tensor(state, dtype=torch.float32).to(device)

        # Set model to evaluation mode for action selection
        if not self.is_eval_mode:
            self.agents[agent_idx].eval() 
        
        with torch.no_grad(): # Always use no_grad for action selection
            action_probs, _ = self.agents[agent_idx](state_tensor, agent_idx)
        
        # Restore training mode if not in global evaluation mode
        if not self.is_eval_mode:
            self.agents[agent_idx].train()

        action_probs = action_probs.squeeze()

        # Filter valid actions
        valid_indices_np = np.nonzero(action_state)[0]
        if len(valid_indices_np) == 0:
            raise ValueError(f"Agent {agent_idx}: No valid actions available in action_state during select_action: {action_state}.")

        valid_indices = torch.tensor(valid_indices_np, dtype=torch.long).to(device)
        valid_action_probs = action_probs[valid_indices]

        # Handle NaN or zero probabilities
        if torch.isnan(valid_action_probs).any() or valid_action_probs.sum().item() == 0:
            if len(valid_indices) > 0:
                valid_action_probs = torch.ones_like(valid_action_probs) / len(valid_indices)
            else:
                 raise ValueError(f"Agent {agent_idx}: No valid_indices but sum of action_state was > 0.")
        else:
            valid_action_probs = valid_action_probs / valid_action_probs.sum()
        
        if torch.isnan(valid_action_probs).any():
            raise ValueError(f"Agent {agent_idx}: valid_action_probs still NaN after recovery attempts: {valid_action_probs}")

        # Sample action
        selected_local_index = torch.multinomial(valid_action_probs, 1).item()
        selected_action = valid_indices[selected_local_index].item()
        action_probability_to_return = valid_action_probs[selected_local_index].item()
        
        return selected_action, action_probability_to_return

    def store_transition(self, agent_idx, state, action, reward, done, old_prob):
        """
        Store experience transition for training.
        
        CHANGES: Enhanced validation and evaluation mode handling
        
        Args:
            agent_idx: Index of the agent
            state: State observation
            action: Action taken
            reward: Reward received
            done: Episode termination flag
            old_prob: Action probability from old policy
        """
        # Skip storing in evaluation mode
        if self.is_eval_mode:
            return

        # Input validation
        if not isinstance(state, (list, np.ndarray)):
            raise ValueError(f"State must be a list or array, but got {type(state)}, {state}.")
        if not isinstance(action, int):
            raise ValueError(f"Action must be an integer, but got {type(action)}, {action}.")
        if not isinstance(reward, (int, float)):
            raise ValueError(f"Reward must be a number, but got {type(reward)}, {reward}.")
        
        self.trajectories[agent_idx].append((state, action, reward, done, old_prob))

    def compute_loss(self, agent, agent_idx, old_probs, states, actions, rewards, dones):
        # ... (compute_loss method remains unchanged) ...
        try:
            states_tensor = torch.tensor(np.array(states), dtype=torch.float32).to(device)
        except ValueError as e:
            raise ValueError(f"Invalid states format: {states}. Ensure states are consistent.") from e

        actions_tensor = torch.tensor(actions, dtype=torch.int64).to(device)
        rewards_tensor = torch.tensor(rewards, dtype=torch.float32).to(device)
        dones_tensor = torch.tensor(dones, dtype=torch.float32).to(device)
        old_probs_tensor = torch.tensor(old_probs, dtype=torch.float32).to(device)
        
        action_probs_full, state_values = agent(states_tensor, agent_idx)
        current_action_probs = action_probs_full.gather(1, actions_tensor.unsqueeze(-1)).squeeze(-1)
        state_values = state_values.squeeze(-1)
        
        ratio = current_action_probs / (old_probs_tensor + 1e-10)
        advantages_for_actor = rewards_tensor + self.gamma * state_values * (1 - dones_tensor) - state_values.detach()
        
        surrogate1 = ratio * advantages_for_actor
        surrogate2 = torch.clamp(ratio, 1 - self.clip_param, 1 + self.clip_param) * advantages_for_actor
        actor_loss = -torch.min(surrogate1, surrogate2).mean()
        
        critic_target = rewards_tensor
        critic_loss = nn.MSELoss()(state_values, critic_target)
        
        entropy = -torch.sum(action_probs_full * torch.log(action_probs_full + 1e-10), dim=-1).mean()

        self.value_losses[agent_idx].append(critic_loss.item())
        self.policy_entropy[agent_idx].append(entropy.item())

        return actor_loss + critic_loss - 0.01 * entropy


    def update(self):
        # Check evaluation mode flag
        if self.is_eval_mode:
            # Clear trajectories even in evaluation mode to prevent memory leaks or interference from old data
            self.trajectories = [[] for _ in range(self.num_agents)]
            # print("Evaluation mode: Skipping policy update.") # Optional debug info
            return # If in evaluation mode, don't perform any updates

        # ... (Original update logic starts here) ...
        for agent_idx, trajectory in enumerate(self.trajectories):
            if not trajectory:
                continue
            try:
                states, actions, rewards, dones, old_probs = zip(*trajectory)
                
                if np.isnan(rewards).any():
                    print(f"[Error] Agent {agent_idx}: NaN detected in rewards before loss computation. Trajectory: {trajectory}")
                    self.trajectories[agent_idx] = [] 
                    continue

                loss = self.compute_loss(self.agents[agent_idx], agent_idx, old_probs, states, actions, rewards, dones)
                
                if torch.isnan(loss):
                    print(f"[Error] Agent {agent_idx}: Loss is NaN. Skipping optimizer step. Review reward/state/action values.")
                    self.trajectories[agent_idx] = [] 
                    continue

                optimizer = self.optimizers[agent_idx]
                optimizer.zero_grad()
                loss.backward()

                grad_norm_val = 0.0
                params_with_grad = [p for p in self.agents[agent_idx].parameters() if p.grad is not None]
                if params_with_grad:
                    total_norm = torch.norm(torch.stack([torch.norm(p.grad.detach(), 2) for p in params_with_grad]), 2)
                    grad_norm_val = total_norm.item()
                self.gradient_norms[agent_idx].append(grad_norm_val)
                
                optimizer.step()

                total_reward_for_logging = sum(r for s, a, r, d, p in trajectory) 
                self.update_counts[agent_idx] += 1
                if self.update_counts[agent_idx] == 1:
                    self.cumulative_rewards[agent_idx].append(-total_reward_for_logging) 
                else:
                    prev_avg = self.cumulative_rewards[agent_idx][-1]
                    new_avg = prev_avg + (-total_reward_for_logging - prev_avg) / self.update_counts[agent_idx]
                    self.cumulative_rewards[agent_idx].append(new_avg)
            except Exception as e:
                print(f"Error updating agent {agent_idx}: {e}")
                traceback.print_exc() 
                continue
        self.trajectories = [[] for _ in range(self.num_agents)] # Clear trajectories


    def log_trajectory(self, agent_idx):
        trajectory = self.trajectories[agent_idx]
        print(f"[DEBUG] Trajectory for agent {agent_idx}:")
        for idx, (state, action, reward, done, old_prob) in enumerate(trajectory):
            print(f"  Step {idx}: state={state}, action={action}, reward={reward}, done={done}, old_prob={old_prob}")
            
    def load_from_csv(self, folder_path):
        """
        Load policy parameters for all agents from CSV files.
        folder_path: Directory path containing the CSV files
        """
        print(f"Attempting to load model parameters from CSV files in {folder_path}...")
        for idx, agent in enumerate(self.agents):
            # Critical: Ensure Actor network is built before loading parameters
            # Since Actor is dynamically created, if there was no previous forward call, actors might be None
            # We need action_space_func and an example state (or its dimensions) to initialize it
            if agent.actors is None:
                # print(f"Agent {idx} actor is None. Initializing before loading from CSV.")
                # Use cached state_dim and action_space_func to initialize
                # ActorCritic._ensure_actors_initialized needs agent_idx and state_dim
                # state_dim for this agent is self.state_dims_cache[idx]
                agent._ensure_actors_initialized(idx, example_state_for_size=None) # Pass None, it will use cached state_dim


            actor_file = os.path.join(folder_path, f"agent_{idx}_actor.csv")
            critic_file = os.path.join(folder_path, f"agent_{idx}_critic.csv")
            
            actor_loaded = False
            if os.path.exists(actor_file):
                if agent.actors is not None: # Check again because _ensure_actors_initialized might fail
                    try:
                        with open(actor_file, 'r') as f:
                            # Storing parameters from model to match shapes if needed
                            actor_model_params = {name: param for name, param in agent.actors.named_parameters()}
                            reader = csv.reader(f)
                            for row in reader:
                                if not row: continue # Skip empty rows
                                name_from_csv, *data_str = row
                                if name_from_csv in actor_model_params:
                                    param_to_load = actor_model_params[name_from_csv]
                                    try:
                                        loaded_data = np.array(data_str, dtype=np.float32)
                                        param_to_load.data.copy_(torch.tensor(loaded_data).view_as(param_to_load.data).to(device))
                                        actor_loaded = True
                                    except ValueError as ve:
                                        print(f"ValueError for agent {idx} actor param {name_from_csv}: {ve}. Data: {data_str[:10]}")
                                    except RuntimeError as re:
                                        print(f"RuntimeError for agent {idx} actor param {name_from_csv}: {re}. Expected shape {param_to_load.data.shape}")
                                # else:
                                #     print(f"Warning: Param {name_from_csv} from CSV not found in agent {idx} actor model.")
                        if actor_loaded: print(f"Agent {idx} actor parameters loaded from {actor_file}")
                    except Exception as e:
                        print(f"Error processing actor CSV {actor_file} for agent {idx}: {e}")
                else:
                    print(f"Agent {idx} actor still None after init attempt. Cannot load from {actor_file}.")
            # else:
            #     print(f"Actor CSV file not found for agent {idx}: {actor_file}")
            
            critic_loaded = False
            if os.path.exists(critic_file):
                try:
                    with open(critic_file, 'r') as f:
                        critic_model_params = {name: param for name, param in agent.critic.named_parameters()}
                        reader = csv.reader(f)
                        for row in reader:
                            if not row: continue
                            name_from_csv, *data_str = row
                            if name_from_csv in critic_model_params:
                                param_to_load = critic_model_params[name_from_csv]
                                try:
                                    loaded_data = np.array(data_str, dtype=np.float32)
                                    param_to_load.data.copy_(torch.tensor(loaded_data).view_as(param_to_load.data).to(device))
                                    critic_loaded = True
                                except ValueError as ve:
                                    print(f"ValueError for agent {idx} critic param {name_from_csv}: {ve}. Data: {data_str[:10]}")
                                except RuntimeError as re:
                                     print(f"RuntimeError for agent {idx} critic param {name_from_csv}: {re}. Expected shape {param_to_load.data.shape}")
                            # else:
                            #    print(f"Warning: Param {name_from_csv} from CSV not found in agent {idx} critic model.")
                    if critic_loaded: print(f"Agent {idx} critic parameters loaded from {critic_file}")
                except Exception as e:
                    print(f"Error processing critic CSV {critic_file} for agent {idx}: {e}")
            # else:
            #    print(f"Critic CSV file not found for agent {idx}: {critic_file}")

        print(f"Finished attempt to load model parameters from {folder_path}.")

                
    def save_to_csv(self, folder_path):
        # Update self.current_results_folder so gradient_norms.csv is also saved here
        self.current_results_folder = folder_path
        os.makedirs(folder_path, exist_ok=True)

        for idx, agent in enumerate(self.agents):
            # Ensure actor is initialized before saving (e.g., through a forward pass)
            if agent.actors is None:
                # print(f"Warning: Agent {idx} actor is None during save. Attempting to initialize.")
                agent._ensure_actors_initialized(idx) # Attempt initialization
            
            if agent.actors is not None:
                actor_params = []
                for name, param in agent.actors.named_parameters():
                    actor_params.append((name, param.data.cpu().numpy()))
                
                actor_file = os.path.join(folder_path, f"agent_{idx}_actor.csv")
                try:
                    with open(actor_file, 'w', newline='') as f: # Ensure newline='' for csv
                        writer = csv.writer(f)
                        for name, data in actor_params:
                            writer.writerow([name] + list(data.flatten()))
                except Exception as e:
                    print(f"Error saving actor CSV for agent {idx}: {e}")
            # else:
            #     print(f"Agent {idx} actor is still None. Cannot save actor parameters.")
            
            critic_params = []
            for name, param in agent.critic.named_parameters():
                critic_params.append((name, param.data.cpu().numpy()))
            
            critic_file = os.path.join(folder_path, f"agent_{idx}_critic.csv")
            try:
                with open(critic_file, 'w', newline='') as f: # Ensure newline=''
                    writer = csv.writer(f)
                    for name, data in critic_params:
                        writer.writerow([name] + list(data.flatten()))
            except Exception as e:
                print(f"Error saving critic CSV for agent {idx}: {e}")

        print(f"Model parameters saved to CSV files in {folder_path}.")


    def plot_metrics(self, folder_path, window_size=1):
        # (plot_metrics code is consistent with the previous version that fixed NaN/empty list issues, omitted here to reduce duplication)
        # ... (Ensure folder_path is used correctly here and there is data to plot) ...
        def smooth(data, window_size):
            if len(data) < window_size: return data 
            return np.convolve(data, np.ones(window_size) / window_size, mode='valid')

        os.makedirs(folder_path, exist_ok=True)

        def _plot_metric_internal(data_all_agents, metric_name, color, aggregate_func=np.mean):
            if not data_all_agents or not any(data_all_agents):
                return
            
            valid_data_for_min_len = [d for d in data_all_agents if d] 
            if not valid_data_for_min_len: return
            min_len = min(len(d) for d in valid_data_for_min_len)
            if min_len == 0 : return

            aggregated_data = []
            if aggregate_func == np.sum :
                 aggregated_data = [np.sum([agent_data[i] for agent_data in valid_data_for_min_len if i < len(agent_data)]) for i in range(min_len)]
            else: 
                 aggregated_data = [np.mean([agent_data[i] for agent_data in valid_data_for_min_len if i < len(agent_data)]) for i in range(min_len)]

            if not aggregated_data: return
            smoothed_data = smooth(aggregated_data, window_size)
            if len(smoothed_data) == 0: return

            plt.figure(figsize=(8, 6))
            plt.plot(smoothed_data, label=metric_name, color=color)
            plt.title(metric_name)
            plt.xlabel("Update Step")
            plt.ylabel(metric_name)
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(folder_path, f"{metric_name.replace(' ', '_').lower()}.png"))
            plt.close()

        _plot_metric_internal(self.cumulative_rewards, "Cumulative Rewards", "blue", aggregate_func=np.sum)
        if any(self.value_losses):
            _plot_metric_internal(self.value_losses, "Value Losses", "orange", aggregate_func=np.mean)
        if any(self.policy_entropy):
            _plot_metric_internal(self.policy_entropy, "Policy Entropy", "green", aggregate_func=np.mean)

        
    def save_metrics_to_csv(self, folder_path):
        # (save_metrics_to_csv code is consistent with the previous version that fixed NaN/empty list issues, omitted)
        # ... (Ensure folder_path is used correctly here) ...
        os.makedirs(folder_path, exist_ok=True)
        def _save_csv_aggregated(data_all_agents, metric_name_suffix, aggregate_func=np.mean):
            if not data_all_agents or not any(data_all_agents): return
            valid_data_for_min_len = [d for d in data_all_agents if d]
            if not valid_data_for_min_len: return
            min_len = min(len(d) for d in valid_data_for_min_len)
            if min_len == 0: return

            aggregated_data = []
            if aggregate_func == np.sum:
                aggregated_data = [np.sum([agent_data[i] for agent_data in valid_data_for_min_len if i < len(agent_data)]) for i in range(min_len)]
            else: 
                aggregated_data = [np.mean([agent_data[i] for agent_data in valid_data_for_min_len if i < len(agent_data)]) for i in range(min_len)]

            if not aggregated_data: return
            file_path = os.path.join(folder_path, f"{metric_name_suffix}.csv") # Use suffix directly as name
            with open(file_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Step", metric_name_suffix])
                for step, value in enumerate(aggregated_data):
                    writer.writerow([step, value])
            # print(f"{metric_name_suffix} saved to {file_path}")

        _save_csv_aggregated(self.cumulative_rewards, "cumulative_rewards", aggregate_func=np.sum)
        if any(self.value_losses):
            _save_csv_aggregated(self.value_losses, "value_losses", aggregate_func=np.mean)
        if any(self.policy_entropy):
            _save_csv_aggregated(self.policy_entropy, "policy_entropy", aggregate_func=np.mean)

        
    def save_gradient_norms_to_csv(self, folder_path):
        # (save_gradient_norms_to_csv code is consistent with the previous version that fixed NaN/empty list issues, omitted)
        # ... (Ensure folder_path is used correctly here, not self.gradient_csv_file) ...
        os.makedirs(folder_path, exist_ok=True)
        # gradient_csv_file_path = os.path.join(folder_path, self.gradient_csv_file_basename)
        # The self.gradient_csv_file_basename might be just "gradient_norms.csv"
        # We want to save it *inside* the specific folder_path for this run.
        gradient_csv_file_path = os.path.join(folder_path, "gradient_norms.csv")


        max_steps = 0
        if self.gradient_norms and any(self.gradient_norms):
            valid_grad_norms = [gn for gn in self.gradient_norms if gn] 
            if valid_grad_norms:
                 max_steps = max(len(grad_norms) for grad_norms in valid_grad_norms)
            else: return
        else: return
        if max_steps == 0: return

        data_to_write = []
        for step in range(max_steps):
            row = [step]
            for agent_idx in range(self.num_agents):
                if agent_idx < len(self.gradient_norms) and self.gradient_norms[agent_idx] and step < len(self.gradient_norms[agent_idx]):
                    row.append(self.gradient_norms[agent_idx][step])
                else:
                    row.append(None)
            data_to_write.append(row)

        with open(gradient_csv_file_path, mode="w", newline="") as file:
            writer = csv.writer(file)
            header = ["Update Step"] + [f"Agent {i} Gradient Norm" for i in range(self.num_agents)]
            writer.writerow(header)
            writer.writerows(data_to_write)
        # print(f"Gradient norms saved to {gradient_csv_file_path}")


    def plot_gradient_norms(self, folder_path, window_size=1):
        # (plot_gradient_norms code is consistent with the previous version that fixed NaN/empty list issues, omitted)
        # ... (Ensure folder_path is used correctly here) ...
        def smooth(data, window_size):
            if len(data) < window_size: return data
            return np.convolve(data, np.ones(window_size) / window_size, mode='valid')

        os.makedirs(folder_path, exist_ok=True)

        for agent_idx, grad_norms in enumerate(self.gradient_norms):
            if not grad_norms: continue
            smoothed_grad_norms = smooth(grad_norms, window_size)
            if len(smoothed_grad_norms) == 0: continue

            plt.figure(figsize=(8, 6))
            plt.plot(smoothed_grad_norms, label=f"Agent {agent_idx} Gradient Norm")
            plt.title(f"Gradient Norm - Agent {agent_idx}")
            plt.xlabel("Update Step")
            plt.ylabel("Gradient Norm")
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(folder_path, f"gradient_norm_agent_{agent_idx}.png"))
            plt.close()