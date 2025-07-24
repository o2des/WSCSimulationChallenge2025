# File path: strategy_making/default.py


class Default:
    """Default strategy-making class for port simulation."""

    def __init__(self, wsc_port=None):
        self.wsc_port = wsc_port

    def allocated_berth(self, waiting_vessel_list):
        """
        Allocate a berth for the given vessel. Default logic uses FIFO.
        """
        allocated_berth = None
        allocated_vessel = None
        current_idle_berths = self.wsc_port.berth_being_idle.completed_list if self.wsc_port else []

        if current_idle_berths and len(waiting_vessel_list) > 0:
            # Example: allocate the earliest idle berth and vessel
            allocated_berth = current_idle_berths[0]
            allocated_vessel = waiting_vessel_list[0]

        return (allocated_berth, allocated_vessel)

    def allocated_agvs(self, container):
        """
        Allocate an AGV for the given container. Default logic finds the nearest idle AGV.
        """
        allocated_agv = None
        current_idle_agvs = self.wsc_port.agv_being_idle.completed_list if self.wsc_port else []
        
        from port_simulation.entity.agv import AGV
        if current_idle_agvs:
            # Example: allocate the nearest idle AGV
            allocated_agv = min(
                current_idle_agvs,
                key=lambda agv: AGV.calculate_distance(agv.current_location, container.current_location),
                default=None
            )

        return allocated_agv

    def determine_yard_block(self, agv):
        """
        Determine the yard block to allocate for the given AGV.
        Default logic finds the nearest yard block with free capacity.
        """
        allocated_yard_block = None
        yard_blocks = self.wsc_port.yard_blocks if self.wsc_port else []

        if yard_blocks:
            # Example: find the nearest yard block with available capacity
            available_blocks = [
                block for block in yard_blocks
                if block.capacity > block.reserved_slots + len(block.stacked_containers)
            ]
            from port_simulation.entity.agv import AGV
            if available_blocks:
                allocated_yard_block = min(
                    available_blocks,
                    key=lambda block: AGV.calculate_distance(block.cp, agv.current_location)
                )

        return allocated_yard_block

    def determine_qc(self, container):
        """
        Determine the QC (Quay Crane) for the given container.
        """
        berth = next(
            (b for b in self.wsc_port.berths if b.berthed_vessel and
             b.berthed_vessel.id == container.loading_vessel_id and
             b.berthed_vessel.week > container.week),
            None
        )

        qc = berth.equipped_qcs[berth.current_work_qc]
        berth.current_work_qc += 1
        if berth.current_work_qc == 3:
            berth.current_work_qc = 0

        return qc
