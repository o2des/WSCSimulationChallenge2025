import os
import csv
from datetime import datetime, timedelta
from port_simulation.model.port_sim_model import PortSimModel # Ensure this path is correct
from strategy_making.default import Default
import reinforcing_learning
import numpy as np


class Simulation:
    """Simulation class for running port scenarios."""

    # Removed if_use_trained_rl from run, as loading is handled by MAPPO init
    def run(self, run_index, seed, rl_agent_instance, num_of_agvs):
        # print(f"RL Instance in Simulation.run: {rl_agent_instance}") # For debugging
        
        print("*" * 70)
        print(f"Seed: {seed}, Scenario {run_index}:")
        print("Simulation running...")

        global wsc_port # If you rely on wsc_port being global
        wsc_port = PortSimModel(
            number_of_agvs= num_of_agvs,
            start_time=datetime(2025, 5, 3), # Consider making this configurable
            containers_info_file_url=f"conf/transhipment{run_index}.csv",
            vessel_arrival_times_url=f"conf/vessel_arrival_time{run_index}.csv"
        )
        wsc_port.initialize(seed)

        # DecisionMaker always gets the rl_agent_instance (which could be None, new, or loaded)
        if rl_agent_instance is None:
            from strategy_making.decision_maker_heuristic import DecisionMaker
            wsc_port_decision_maker = DecisionMaker(wsc_port)
        else:
            from strategy_making.decision_maker_learning import DecisionMaker
            wsc_port_decision_maker = DecisionMaker(wsc_port, rl_agent_instance)
        
        wsc_port.berth_being_idle.strategy_maker = wsc_port_decision_maker
        wsc_port.agv_being_idle.strategy_maker = wsc_port_decision_maker
        wsc_port.agv_delivering_to_yard.strategy_maker = wsc_port_decision_maker
        wsc_port.vessel_berthing.strategy_maker = wsc_port_decision_maker
        
        # The original if_use_trained_rl flag from wsc_port.vessel_berthing is removed
        # Its logic is now implicitly handled by whether rl_agent_instance is pre-loaded or not.
        # If you had specific logic tied to wsc_port.vessel_berthing.if_use_trained_rl,
        # you might need to adapt it based on whether rl_agent_instance is not None.
        # For example:
        wsc_port.vessel_berthing.if_use_rl = (rl_agent_instance is not None)

        wsc_port_default = Default(wsc_port)
        wsc_port.berth_being_idle.default_maker = wsc_port_default
        wsc_port.agv_being_idle.default_maker = wsc_port_default
        wsc_port.agv_delivering_to_yard.default_maker = wsc_port_default

        wsc_port.run(duration=timedelta(days=7 * wsc_port.running_weeks))

        for vessel in wsc_port.vessels:
            if vessel.arrival_time and not vessel.start_berthing_time:
                vessel.start_berthing_time = wsc_port.clock_time

        num_of_delayed_vessels = sum(
            1 for vessel in wsc_port.vessels if vessel.arrival_time and vessel.start_berthing_time
            and (vessel.start_berthing_time - vessel.arrival_time > timedelta(hours=2))
        )
        num_of_arrival_vessels = sum(1 for vessel in wsc_port.vessels if vessel.arrival_time)
        
        rate_of_delayed_vessels = (num_of_delayed_vessels / num_of_arrival_vessels) * 100 if num_of_arrival_vessels else 0
        
        valid_service_times = [v.service_time for v in wsc_port.vessels if hasattr(v, 'service_time') and v.service_time is not None]
        avg_service_time = sum(valid_service_times) / num_of_arrival_vessels if num_of_arrival_vessels and valid_service_times else 0.0 # Default to 0.0
        
        valid_waiting_times_seconds = []
        for vessel in wsc_port.vessels:
            if hasattr(vessel, 'start_berthing_time') and vessel.start_berthing_time and \
               hasattr(vessel, 'arrival_time') and vessel.arrival_time:
                valid_waiting_times_seconds.append((vessel.start_berthing_time - vessel.arrival_time).total_seconds())
        
        avg_waiting_time_hours = (sum(valid_waiting_times_seconds) / 3600) / num_of_arrival_vessels if num_of_arrival_vessels and valid_waiting_times_seconds else 0.0 # Default to 0.0

        wsc_port.run(duration=timedelta(days=300))

        # Debug and validate conditions (original logic)
        conditions = {
            "DischargingCondition": wsc_port.warm_up_weeks * wsc_port.container_being_discharged.discharging
                                    == len(wsc_port.container_dwelling.completed_list) * wsc_port.running_weeks,
            "LoadingCondition": wsc_port.warm_up_weeks * wsc_port.container_being_loaded.loading
                                 == len(wsc_port.container_dwelling.completed_list)
                                    * (wsc_port.running_weeks - wsc_port.warm_up_weeks),
            "FlowCondition": wsc_port.container_being_discharged.discharging
                             - wsc_port.container_being_loaded.loading
                             == len(wsc_port.container_dwelling.completed_list),
            "BerthCondition": wsc_port.number_of_berths == len(wsc_port.berth_being_idle.completed_list),
            "VesselCondition": len(wsc_port.vessel_waiting.completed_list) == 0,
            "QCCondition": len(wsc_port.qc_being_idle.completed_list) == wsc_port.number_of_qcs,
            "AGVCondition": wsc_port.number_of_agvs == len(wsc_port.agv_being_idle.completed_list),
            "YCCondition": wsc_port.number_of_ycs == len(wsc_port.yc_repositioning.completed_list)
        }

        if all(conditions.values()): # Only print and return valid results if conditions met
            print("*" * 70)
            print(f"Seed: {seed}, Scenario {run_index}: VALID RUN")
            print(f"Number of delayed vessels: {num_of_delayed_vessels}; "
                  f"Number of arrival vessels: {num_of_arrival_vessels}")
            print(f"Rate of delayed vessels: {rate_of_delayed_vessels:.2f} %")
            print(f"Average service time: {avg_service_time:.2f} hrs")
            print(f"Average waiting time: {avg_waiting_time_hours:.2f} hrs")
            print(f"Average waiting time: {avg_service_time + avg_waiting_time_hours:.2f} hrs")
            print("Simulation completed")
            print("*" * 70)
            # print("Debug Checking:")
            # for condition, status in conditions.items():
            #     print(f"{condition}:{status}")
            return [rate_of_delayed_vessels, avg_service_time, avg_waiting_time_hours, avg_service_time + avg_waiting_time_hours]
        else:
            print("*" * 70)
            print(f"Seed: {seed}, Scenario {run_index}: INVALID RUN (conditions not met)")
            print("Debug Checking for failed run:")
            for condition, status in conditions.items():
                print(f"{condition}:{status}")
            print("*" * 70)
            # Original code had: return self.run(run_index, seed, rl) # This recursive call can be dangerous
            # For now, return NaN or raise an error for invalid runs to avoid infinite loops.
            return [float('nan'), float('nan'), float('nan'), float('nan')] # Indicate an invalid run's results


def main():
    num_of_agvs = 12
    
    # --- Configuration for RL and Model Loading ---
    IF_REINFORCING_LEARNING = True # Master switch for using RL
    
    # **IMPORTANT**: Set this to the folder containing your pre-trained CSV model files
    # Set to None to train from scratch.
    # Example: LOAD_MODEL_FOLDER = r"E:\path\to\your\saved_models\rl_saved_model_12agvs"
    LOAD_MODEL_FOLDER = None  #"rl_loading" <--- SET YOUR PATH HERE IF YOU WANT TO LOAD
    # Configuration for evaluation mode (no policy updates)
    # If True: Model will be loaded without policy updates, used for result reproduction or evaluation
    # If False: Model will continue training after loading
    RUN_IN_EVALUATION_MODE = False  # <--- SET THIS VALUE!
    
    # Folder where new models and all results will be saved for THIS run
    # This will be a unique timestamped folder.
    base_results_folder = "results_output" # Main folder for all results
    current_run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Name the folder based on whether RL is used and AGV count for clarity
    run_type_name = "rl" if IF_REINFORCING_LEARNING else "heuristic"
    model_and_results_folder_this_run = os.path.join(base_results_folder, f"{run_type_name}_{num_of_agvs}agvs_{current_run_timestamp}")
    
    os.makedirs(model_and_results_folder_this_run, exist_ok=True)
    print(f"All outputs for this run (models, metrics, results) will be in: {model_and_results_folder_this_run}")

    rl = None # Initialize rl to None
    # Define state_dims (MUST MATCH THE NETWORK STRUCTURE AND (action_state + env_state) LENGTH)
    # For the original network:
    # Agent 0 (Berth): action_state is 4 (num_berths). If env_state is empty, state_dim = 4.
    # Agent 1 (AGV): action_state is num_of_agvs. If env_state is empty, state_dim = num_of_agvs.
    # Agent 2 (Yard Block): action_state is 16 (num_yard_blocks). If env_state is empty, state_dim = 16.
    # Agent 3 (vessels): action_state is 3 (max_vessels_in_decision_pool). If env_state is empty, state_dim = 3.
    # **If you add features to env_state in DecisionMaker, you MUST update these dimensions.**
    current_state_dims = [4, num_of_agvs, 16, 3] # Assuming env_state is currently empty

    if IF_REINFORCING_LEARNING:
        print(f"Initializing Reinforcement Learning Agent (MAPPO)...")
        rl = reinforcing_learning.MAPPO(
            state_dims=current_state_dims,
            action_space_funcs=[
                lambda state, agent_idx: 4,  # Berth allocation
                lambda state, agent_idx: num_of_agvs,  # AGV allocation
                lambda state, agent_idx: 16,  # Yard block allocation
                lambda state, agent_idx: 3,  # Vessel selection
            ],
            num_agents=4,
            # CHANGES: Added hyperparameter tuning capabilities
            lr=5e-3,           # Learning rate adjustment
            gamma=0.95,        # Discount factor adjustment
            clip_param=0.1,    # PPO clipping parameter adjustment
            load_from_folder_path=LOAD_MODEL_FOLDER
        )
        if LOAD_MODEL_FOLDER:
            print(f"RL Agent initialized. Attempted to load model from: {LOAD_MODEL_FOLDER}")
            # If a model is specified to load and you want to run in evaluation mode
            if RUN_IN_EVALUATION_MODE:
                rl.set_eval_mode(True) # Call the new method to set RL agent to evaluation mode
            else:
                rl.set_eval_mode(False) # Ensure training mode (if it was previously in evaluation mode)
                print("RL Agent will continue training.")
        else:
            print(f"RL Agent initialized. Training new model (no load path provided).")

    # File paths for simulation results CSVs (within the unique run folder)
    delayed_rate_file = os.path.join(model_and_results_folder_this_run, f"{run_type_name}_delayed_rate_{num_of_agvs}agvs.csv")
    avg_service_time_file = os.path.join(model_and_results_folder_this_run, f"{run_type_name}_avg_service_time_{num_of_agvs}agvs.csv")
    avg_waiting_time_file = os.path.join(model_and_results_folder_this_run, f"{run_type_name}_avg_waiting_time_{num_of_agvs}agvs.csv")
    avg_total_time_file = os.path.join(model_and_results_folder_this_run, f"{run_type_name}_avg_total_time_{num_of_agvs}agvs.csv")

    total_delayed_rate = 0
    total_avg_service_time = 0
    total_avg_waiting_time = 0
    total_avg_time = 0
    valid_runs_count = 0

    seeds = [95036]  # 95036, 73386, 77742, 18078, 17273, 82576, 89676, 6069, 61009, 43540
    num_of_scenarios = 1 # Reduced for demo

    with open(delayed_rate_file, mode="w", newline="") as delayed_rate_csv, \
         open(avg_service_time_file, mode="w", newline="") as service_time_csv, \
         open(avg_waiting_time_file, mode="w", newline="") as waiting_time_csv, \
         open(avg_total_time_file, mode="w", newline="") as total_time_csv:
        
        delayed_rate_writer = csv.writer(delayed_rate_csv)
        service_time_writer = csv.writer(service_time_csv)
        waiting_time_writer = csv.writer(waiting_time_csv)
        total_time_writer = csv.writer(total_time_csv)

        scenario_headers = [f"Scenario_{i}" for i in range(num_of_scenarios)]
        delayed_rate_writer.writerow(["Seed"] + scenario_headers)
        service_time_writer.writerow(["Seed"] + scenario_headers)
        waiting_time_writer.writerow(["Seed"] + scenario_headers)
        total_time_writer.writerow(["Seed"] + scenario_headers)

        for seed_value in seeds: # Renamed to avoid conflict
            delayed_rate_row = [seed_value]
            service_time_row = [seed_value]
            waiting_time_row = [seed_value]
            total_time_row = [seed_value]

            for index in range(num_of_scenarios):
                sim = Simulation()
                # Pass rl instance to run method. The if_use_trained_rl flag is removed from sim.run
                values = sim.run(index, seed_value, rl, num_of_agvs)

                if values and not any(np.isnan(values)): # Check if results are valid
                    delayed_rate, avg_service_time, avg_waiting_time, avg_total_time = values
                    
                    delayed_rate_row.append(delayed_rate)
                    service_time_row.append(avg_service_time)
                    waiting_time_row.append(avg_waiting_time)
                    total_time_row.append(avg_total_time)

                    total_delayed_rate += delayed_rate
                    total_avg_service_time += avg_service_time
                    total_avg_waiting_time += avg_waiting_time
                    total_avg_time += avg_total_time

                    valid_runs_count +=1
                else: # Handle NaN results from invalid sim runs
                    delayed_rate_row.append('N/A_InvalidRun')
                    service_time_row.append('N/A_InvalidRun')
                    waiting_time_row.append('N/A_InvalidRun')
                    total_time_row.append('N/A_InvalidRun')

            delayed_rate_writer.writerow(delayed_rate_row)
            service_time_writer.writerow(service_time_row)
            waiting_time_writer.writerow(waiting_time_row)
            total_time_writer.writerow(total_time_row)

    if valid_runs_count > 0:
        avg_overall_delayed_rate = total_delayed_rate / valid_runs_count
        avg_overall_service_time = total_avg_service_time / valid_runs_count
        avg_overall_waiting_time = total_avg_waiting_time / valid_runs_count
        avg_overall_total_time = total_avg_time / valid_runs_count

        print(f"Overall Average rate of delayed vessels (for {valid_runs_count} valid runs): {avg_overall_delayed_rate:.2f} %")
        print(f"Overall Average service time (for {valid_runs_count} valid runs): {avg_overall_service_time:.2f} hrs")
        print(f"Overall Average waiting time (for {valid_runs_count} valid runs): {avg_overall_waiting_time:.2f} hrs")
        print(f"Overall Average total time (for {valid_runs_count} valid runs): {avg_overall_total_time:.2f} hrs")
    else:
        print("No valid simulation runs completed to calculate overall averages.")

    if rl is not None: # If RL was used
        print(f"Saving RL model (if updated) to: {model_and_results_folder_this_run}")
        rl.save_to_csv(model_and_results_folder_this_run) # Save model parameters to the unique run folder
    
        print(f"Saving RL metrics to: {model_and_results_folder_this_run}")
        rl.save_metrics_to_csv(model_and_results_folder_this_run)
        rl.save_gradient_norms_to_csv(model_and_results_folder_this_run)
        
        print(f"Plotting RL metrics to: {model_and_results_folder_this_run}")
        # Adjust window_size for smoothing based on number of updates (e.g., num_of_scenarios * num_seeds)
        # For now, a small fixed value or related to num_of_scenarios
        smoothing_window = max(1, (len(seeds) * num_of_scenarios) // 10 if (len(seeds) * num_of_scenarios) > 0 else 1)
        rl.plot_metrics(model_and_results_folder_this_run, window_size=smoothing_window)
        rl.plot_gradient_norms(model_and_results_folder_this_run, window_size=smoothing_window)

if __name__ == "__main__":
    # --- How to use ---
    # 1. To train a new model and save it:
    #    - Set IF_REINFORCING_LEARNING = True
    #    - Set LOAD_MODEL_FOLDER = None
    #    - Run the script. Model and results will be in a new timestamped folder inside 'results_output'.

    # 2. To load a previously saved model (e.g., from CSVs in 'conf/rl_saved_model_12agvs')
    #    and continue training/running:
    #    - Set IF_REINFORCING_LEARNING = True
    #    - Set LOAD_MODEL_FOLDER = r"conf/rl_saved_model_12agvs"  # <--- YOUR ACTUAL PATH
    #    - Run the script. The loaded model will be used.
    #      Any *new* saves (model, metrics) will go into a new timestamped folder in 'results_output'.

    # 3. To run with default heuristics only (no RL):
    #    - Set IF_REINFORCING_LEARNING = False
    #    - LOAD_MODEL_FOLDER will be ignored.
    #    - Results will be saved in a 'default_strategy_results' folder (or similar, based on logic).

    main()