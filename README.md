# WSC SimChallenge 2025 - Port Simulation

## Project Overview

This project is a port simulation system for WSC SimChallenge 2025, designed to simulate the operations of a container port, including vessel arrivals, berth allocation, container loading/unloading, AGV transportation, and other related operations. Participants need to optimize decision-making strategies to improve port operational efficiency and reduce the average waiting and service time of vessels.

## File Structure

The main file structure of the project is as follows:

```
├── __init__.py                  # Main program entry, containing Simulation class and main function
├── reinforcing_learning.py      # Reinforcement learning implementation (MAPPO algorithm)
├── activity/                    # Activity-related classes
│   └── base_activity.py         # Base activity class
├── commons/                     # Common utility classes
│   ├── file_config.py           # File configuration
│   └── time_tools.py            # Time tools
├── conf/                        # Configuration file directory
│   ├── QC_controlpoint.csv      # Quay Crane control point configuration
│   ├── YC_controlpoint.csv      # Yard Crane control point configuration
│   ├── transhipment*.csv        # Container transshipment information (scenarios 0-29)
│   └── vessel_arrival_time*.csv # Vessel arrival times (scenarios 0-29)
├── file_reader/                 # File reading tools
│   └── file_reader.py           # File reader class
├── o2despy/                     # Discrete event simulation framework
│   ├── sandbox.py               # Simulation sandbox
│   ├── entity.py                # Entity class
│   └── action.py                # Action class
├── port_simulation/             # Port simulation core code
│   ├── entity/                  # Port entities
│   │   ├── agv.py               # AGV entity
│   │   ├── berth.py             # Berth entity
│   │   ├── container.py         # Container entity
│   │   ├── qc.py                # Quay Crane entity
│   │   ├── vessel.py            # Vessel entity
│   │   └── yc.py                # Yard Crane entity
│   └── model/                   # Models
│       └── port_sim_model.py    # Port simulation model
├── strategy_making/             # Decision strategies
│   ├── decision_maker_heuristic.py # Heuristic decision maker
│   ├── decision_maker_learning.py  # Reinforcement learning-based decision maker
│   └── default.py                  # Default strategy
├── results_output/              # Results output directory
└── rl_loading/                  # Pre-trained model loading directory
```

## Port Simulation Features and Components

The Port Simulation system is a discrete event simulation-based port operation system that primarily simulates the following processes:

1. **Vessel Arrival and Berth Allocation**: Vessels arrive at the port according to scheduled times and wait for berth allocation.
2. **Container Loading/Unloading**: After berthing, Quay Cranes (QCs) perform container loading and unloading operations.
3. **AGV Transportation**: Automated Guided Vehicles (AGVs) are responsible for transporting containers from the quayside to the yard or from the yard to the quayside.
4. **Yard Operations**: Yard Cranes (YCs) are responsible for stacking and retrieving containers in the Yard Blocks.

The core components of the system include:

- **PortSimModel**: The core model of the entire port simulation, managing all entities and activities.
- **Entities**: Including Vessels, Berths, Quay Cranes (QCs), AGVs, Yard Cranes (YCs), Containers, etc.
- **Activities**: Defining various operational processes such as vessel waiting, berth allocation, container loading/unloading, etc.
- **Decision Maker**: Responsible for making various decisions such as berth allocation, AGV scheduling, yard block selection, etc.

## Decision-Maker and Reinforcing Learning

### Decision Maker

There are two types of decision makers in the project:

1. **Decision Maker (Heuristic)**: `decision_maker_heuristic.py`
   - Uses predefined rules and logic for decision making
   - Main methods include:
     - `customeized_allocated_berth`: Allocates berths to vessels
     - `customeized_allocated_agvs`: Allocates AGVs to containers
     - `customeized_determine_yard_block`: Determines yard blocks for AGVs

2. **Decision Maker (Reinforcement Learning)**: `decision_maker_learning.py`
   - Uses reinforcement learning algorithms for decision making
   - Has the same main methods as the heuristic approach, but decisions are made by the reinforcement learning model
   - Additionally includes the `get_reward_and_update` method for calculating rewards and updating the reinforcement learning model

### Reinforcing Learning

The reinforcement learning implementation is in the `reinforcing_learning.py` file, using the MAPPO (Multi-Agent Proximal Policy Optimization) algorithm.

#### Agents and Actions

There are 4 agents in the system:

1. **Berth Allocation Agent (Agent 0)**: Responsible for deciding which berth to allocate to which vessel
   - State dimension: 4 (number of berths)
   - Action space: 4 (available berths)

2. **AGV Allocation Agent (Agent 1)**: Responsible for deciding which AGV to allocate to a container
   - State dimension: Number of AGVs (default is 12)
   - Action space: Number of AGVs

3. **Yard Block Allocation Agent (Agent 2)**: Responsible for deciding which yard block to allocate to a container
   - State dimension: 16 (number of yard blocks)
   - Action space: 16 (available yard blocks)

4. **Vessel Selection Agent (Agent 3)**: Responsible for deciding which waiting vessel to process
   - State dimension: 3 (maximum number of vessels in the decision pool)
   - Action space: 3 (available vessels)

These agents are set up in the `main` function of `__init__.py` (around line 150):

```python
rl = reinforcing_learning.MAPPO(
    state_dims=current_state_dims, # [4, num_of_agvs, 16, 3]
    action_space_funcs=[
        lambda state, agent_idx: 4, #berth
        lambda state, agent_idx: num_of_agvs, # agv
        lambda state, agent_idx: 16, #yard block
        lambda state, agent_idx: 3, #vessel
    ],
    num_agents=4,
    load_from_folder_path=LOAD_MODEL_FOLDER
)
```

#### Reward Mechanism and Updates

The system uses a Delayed Reward mechanism:

1. In `decision_maker_learning.py`, states and actions are recorded during each decision, but rewards are not calculated immediately
2. When a vessel completes service and leaves the port, the reward (negative service time) is calculated in the `get_reward_and_update` method
3. The reward is then passed back to all agents involved in serving that vessel, and the policy is updated

This delayed reward mechanism better aligns with the characteristics of actual port operations, as the effects of decisions can only be evaluated after a vessel completes its service.

## Key Switches and Configurations

There are several key configuration options in the `__init__.py` file:

1. **IF_REINFORCING_LEARNING** (around line 129)
   - Sets whether to use reinforcement learning
   - `True`: Use reinforcement learning (`decision_maker_learning.py`)
   - `False`: Use heuristic methods (`decision_maker_heuristic.py`)

2. **LOAD_MODEL_FOLDER** (around line 134)
   - Sets the folder path for loading pre-trained models
   - If set to `None`, a new model will be trained from scratch
   - For example: Setting it to `"rl_loading"` will load pre-trained models from that directory

3. **RUN_IN_EVALUATION_MODE** (around line 138)
   - Sets whether to run in evaluation mode
   - `True`: The model will be loaded but not updated (for result reproduction or evaluation)
   - `False`: The model will continue to be trained after loading

## Competition Rules and Tips

1. **Allowed Modifications**:
   - You can modify all code except the model logic
   - You can choose one method (or combine both methods) from heuristic and reinforcement learning to guide port operations

2. **Main Modification Points**:
   - `decision_maker_heuristic.py`
   - `decision_maker_learning.py`
   - `reinforcing_learning.py`
   - `__init__.py`

3. **Optimization Goal**:
   - Optimize the average waiting time and service time of vessels (total time from vessel arrival to completion of cargo handling and departure) without modifying the simulation logic

4. **Using Pre-trained Models**:
   - After training, models are saved in the `results_output` directory
   - To use pre-trained models, copy the model files (such as `agent_0_actor.csv`, etc.) to the `rl_loading` directory
   - Set `LOAD_MODEL_FOLDER="rl_loading"` and `RUN_IN_EVALUATION_MODE=True`

5. **Understanding the Code**:
   - If you find it difficult to understand the program logic, you can use AI tools (such as Trae) to help analyze the code
   - The organizers have tested that this method can quickly help beginners understand the program

## Results Output

After running the program, results will be saved in a timestamp folder under the `results_output` directory, including:

- Delay rate (`delayed_rate_*.csv`)
- Average service time (`avg_service_time_*.csv`)
- Average waiting time (`avg_waiting_time_*.csv`)
- If using reinforcement learning, model parameters and training metrics will also be saved

Good luck to all participants!