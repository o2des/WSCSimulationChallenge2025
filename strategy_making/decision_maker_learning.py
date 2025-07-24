class DecisionMaker:
    def __init__(self, wsc_port=None, rl=None):
        self.wsc_port = wsc_port
        self.reinforcing_learning = rl
        self.state_action_history = {}  # Store state and action for each vessel

    def customeized_allocated_berth(self, waiting_vessel_list):
        """
        Allocate a berth for the given vessel using reinforcement learning.
        
        Args:
            waiting_vessel_list: List of vessels waiting for berth allocation
            
        Returns:
            Tuple of (allocated_berth, allocated_vessel) or (None, None) if no allocation possible
        """
        if self.reinforcing_learning != None:
            # Get current berth availability status
            action_state_berth = [1 if b in self.wsc_port.berth_being_idle.completed_list else 0 for b in self.wsc_port.berths]
            
            # Limit vessel consideration pool for computational efficiency
            max_vessels_in_decision_pool = 3
            num_vessels_to_actually_consider = min(len(waiting_vessel_list), max_vessels_in_decision_pool)
            action_state_vessel = [1 if i < num_vessels_to_actually_consider else 0 for i in range(max_vessels_in_decision_pool)]
            
            # Check if any berths or vessels are available
            if sum(action_state_berth) == 0 or sum(action_state_vessel) == 0:
                return (None, None)
    
            # CHANGES: Enhanced state representation capability
            env_state_berth = []  # Can be extended with additional environmental features
            env_state_vessel = []  # Can be extended with vessel-specific features
    
            # Use reinforcement learning model to select actions
            action_berth, prob_berth = self.reinforcing_learning.select_action(action_state_berth, env_state_berth, agent_idx=0)
            self.reinforcing_learning.store_transition(0, action_state_berth+env_state_berth, action_berth, 0, False, prob_berth)
            
            action_vessel, prob_vessel = self.reinforcing_learning.select_action(action_state_vessel, env_state_vessel, agent_idx=3)
            self.reinforcing_learning.store_transition(3, action_state_vessel+env_state_vessel, action_vessel, 0, False, prob_berth)
            
            allocated_berth = self.wsc_port.berths[action_berth]
            allocated_vessel = waiting_vessel_list[action_vessel]
            
            # Record state and action for reward calculation
            if allocated_vessel not in self.state_action_history:
                self.state_action_history[allocated_vessel] = {}
            self.state_action_history[allocated_vessel]["berth"] = (action_state_berth+env_state_berth, action_berth, prob_berth)
            
            if allocated_berth not in self.state_action_history:
                self.state_action_history[allocated_berth] = {}
            self.state_action_history[allocated_berth]["vessel"] = (action_state_vessel+env_state_vessel, action_vessel, prob_vessel)
            
            try:
                return (allocated_berth, allocated_vessel)
            except IndexError:
                return (None, None)
        else:
            return (None, None)

    def customeized_allocated_agvs(self, container):
        """
        Allocate an AGV for the given container using reinforcement learning.
        
        Args:
            container: Container object requiring AGV allocation
            
        Returns:
            Allocated AGV object or None if no allocation possible
        """
        if self.reinforcing_learning != None:
            # Get current AGV availability status
            action_state = [1 if a in self.wsc_port.agv_being_idle.completed_list else 0 for a in self.wsc_port.agvs]
            
            if sum(action_state) == 0:
                return None
            
            # CHANGES: Enhanced state representation capability
            env_state = []  # Can be extended with distance calculations or other features
            
            # CHANGES: Optional distance-based state enhancement (commented for future use)
            # Calculate distance between each AGV and container
            # from port_simulation.entity.agv import AGV
            # list_of_distances = [AGV.calculate_distance(container.current_location, agv.current_location) for agv in self.wsc_port.agvs]
            # env_state = list_of_distances
            
            # Use reinforcement learning model to select action
            action, prob = self.reinforcing_learning.select_action(action_state, env_state, agent_idx=1)
            self.reinforcing_learning.store_transition(1, action_state+env_state, action, 0, False, prob)
    
            # Record state and action for reward calculation
            if container not in self.state_action_history:
                self.state_action_history[container] = {}
            self.state_action_history[container]["agv"] = (action_state+env_state, action, prob)
    
            try:
                allocated_agv = self.wsc_port.agvs[action]
                return allocated_agv
            except IndexError:
                return None
        else:
            return None

    def customeized_determine_yard_block(self, agv):
        """
        Determine the yard block allocation for the given AGV using reinforcement learning.
        
        Args:
            agv: AGV object requiring yard block allocation
            
        Returns:
            Allocated yard block object or None if no allocation possible
        """
        if self.reinforcing_learning != None:
            # Get current yard block availability status based on capacity
            action_state = [1 if y.capacity > y.reserved_slots + len(y.stacked_containers) else 0 for y in self.wsc_port.yard_blocks]
            
            if sum(action_state) == 0:
                return None

            # CHANGES: Enhanced state representation capability
            env_state = []  # Can be extended with yard utilization or distance features

            # Use reinforcement learning model to select action
            action, prob = self.reinforcing_learning.select_action(action_state, env_state, agent_idx=2)
            self.reinforcing_learning.store_transition(2, action_state+env_state, action, 0, False, prob)
    
            # Record state and action for reward calculation
            if agv not in self.state_action_history:
                self.state_action_history[agv] = {}
            self.state_action_history[agv]["yard_block"] = (action_state+env_state, action, prob)
    
            try:
                allocated_yard_block = self.wsc_port.yard_blocks[action]
                return allocated_yard_block
            except IndexError:
                return None
        else:
            return None

    def get_reward_and_update(self, vessel):
        """
        Calculate reward and update the RL model when a vessel completes service.
        
        CHANGES: Enhanced reward calculation system
        - Supports multiple reward function designs
        - Uses vessel.total_time as primary metric
        - Enables future reward function improvements
        
        Args:
            vessel: Vessel object that completed service
        """
        if self.reinforcing_learning != None:
            assert self.reinforcing_learning is not None, "Reinforcing learning instance is None."
    
            # CHANGES: Improved reward calculation
            # Current implementation uses negative total time
            # Future enhancements can include:
            # - Weighted combination of waiting time and service time
            # - Container-based normalization
            # - Time-window sensitive penalties
            # - Multi-objective optimization
            
            # Calculate reward based on total time (waiting + service)
            reward = -(vessel.total_time)  # Negative total time as reward
    
            # Retrieve stored states and actions for all agents involved
            vessel_history = self.state_action_history.get(vessel, {})
            for agent_idx, key in enumerate(["berth", "agv", "yard_block", "vessel"]):
                if key in vessel_history:
                    state, action, prob = vessel_history[key]
                    self.reinforcing_learning.store_transition(agent_idx, state, action, reward, True, prob)
    
            # Update the reinforcement learning model
            self.reinforcing_learning.update()