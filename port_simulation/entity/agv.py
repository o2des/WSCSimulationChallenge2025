# File path: port_simulation/entity/agv.py

from datetime import timedelta
from port_simulation.entity.control_point import ControlPoint
from activity.base_activity import BaseActivity


class AGV:
    """Automated Guided Vehicle (AGV)"""

    speed = 4.5  # Speed in meters per second
    left_network_cp = ControlPoint("Left Network Control Point", 0, 100)
    right_network_cp = ControlPoint("Right Network Control Point", 1600, 100)

    def __init__(self, id=None, current_location= None):
        self.id = id
        self.current_location = current_location
        self.loaded_container = None
        self.targeted_yb = None
        self.targeted_qc = None
        self.in_discharging = False

    def __str__(self):
        return f"AGV[{self.id}]"

    @staticmethod
    def calculate_distance(cp1, cp2):
        """Calculate the distance between two control points."""
        if abs(cp1.y_coordinate - cp2.y_coordinate) > 100:  # Travel between quayside and second row YC
            left_route_distance = AGV.manhattan_distance(cp1, AGV.left_network_cp) + \
                                  AGV.manhattan_distance(AGV.left_network_cp, cp2)
            right_route_distance = AGV.manhattan_distance(cp1, AGV.right_network_cp) + \
                                   AGV.manhattan_distance(AGV.right_network_cp, cp2)
            return min(left_route_distance, right_route_distance)
        else:
            return AGV.manhattan_distance(cp1, cp2)

    @staticmethod
    def manhattan_distance(cp1, cp2):
        """Calculate Manhattan distance between two control points."""
        return abs(cp1.y_coordinate - cp2.y_coordinate) + abs(cp1.x_coordinate - cp2.x_coordinate)


    class BeingIdle(BaseActivity):
        """AGV BeingIdle State"""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingIdle", debug_mode=debug_mode, seed=seed)
            self.containers_pending = []
            
            from strategy_making.default import Default
            
            self.strategy_maker = None
            self.default_maker = Default()
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)
    
        def attempt_to_finish(self, agv):
            """Attempt to finish the BeingIdle state."""
            if self.debug_mode:
                print(f"{self.clock_time}  AGV{self.activity_name}.AttemptToFinish({agv})")
            if agv in self.completed_list and self.need_ext_try_finish and agv in self.ready_to_finish_list:
                self.finish(agv)
            elif (agv in self.completed_list and self.need_ext_try_finish and agv not in self.ready_to_finish_list
                  and self.containers_pending):
                selected_agv = self.strategy_maker.customeized_allocated_agvs(self.containers_pending[0]) or \
                               self.default_maker.allocated_agvs(self.containers_pending[0])
    
                selected_agv.loaded_container = self.containers_pending.pop(0)
                selected_agv.loaded_container.agv_taken = selected_agv
                selected_agv.in_discharging = selected_agv.loaded_container.in_discharging
    
                if not selected_agv.in_discharging:
                    qc = self.default_maker.determine_qc(selected_agv.loaded_container)
                    selected_agv.loaded_container.target_qc = qc
                    selected_agv.targeted_qc = qc
    
                self.ready_to_depart_list.append(selected_agv)
                self.finish(selected_agv)
    
        def try_finish(self, obj):
            """Handle external request to finish."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.TryFinish({obj})")
            
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if container:
                self.containers_pending.append(container)
                selected_agv = self.strategy_maker.customeized_allocated_agvs(container) or \
                               self.default_maker.allocated_agvs(container)
                if selected_agv and selected_agv in self.completed_list:
                    selected_agv.loaded_container = self.containers_pending.pop(0)
                    selected_agv.loaded_container.agv_taken = selected_agv
                    selected_agv.in_discharging = selected_agv.loaded_container.in_discharging
    
                    if not selected_agv.in_discharging:
                        qc = self.default_maker.determine_qc(selected_agv.loaded_container)
                        selected_agv.loaded_container.target_qc = qc
                        selected_agv.targeted_qc = qc
    
                    self.ready_to_finish_list.append(selected_agv)
                    self.attempt_to_finish(selected_agv)


    class Picking(BaseActivity):
        """AGV Picking State"""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Picking", debug_mode=debug_mode, seed=seed)
    
        def start(self, agv):
            """Start picking."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.Start({agv})")
            self.hour_counter.observe_change(1)
            self.processing_list.append(agv)
            self.pending_list.remove(agv)
            if agv in self.ready_to_start_list:
                self.ready_to_start_list.remove(agv)
            self.time_span = timedelta(seconds=AGV.calculate_distance(agv.current_location, agv.loaded_container.current_location) / agv.speed)
            self.schedule(lambda: self.complete(agv), self.time_span)
            self.emit_on_start(agv)
    
        def depart(self, agv):
            """Depart after picking."""
            if agv in self.ready_to_depart_list:
                if self.debug_mode:
                    print(f"{self.clock_time}  {self.activity_name}.Depart({agv})")
                self.hour_counter.observe_change(-1)
                self.ready_to_depart_list.remove(agv)
                agv.current_location = agv.loaded_container.current_location
                self.attempt_to_start()

    class DeliveringToYard(BaseActivity):
        """Represents the DeliveringToYard state for AGV."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="DeliveringToYard", debug_mode=debug_mode, seed=seed)
            from strategy_making.default import Default
            self.strategy_maker = None
            self.default_maker = Default()

        def start(self, agv):
            """Start the DeliveringToYard process."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.Start({agv})")
            yard_block = self.strategy_maker.customeized_determine_yard_block(agv) or self.default_maker.determine_yard_block(agv)
            yard_block.reserve_slot()
            agv.targeted_yb = yard_block
            agv.loaded_container.block_stacked = yard_block
            self.hour_counter.observe_change(1)
            self.processing_list.append(agv)
            self.pending_list.remove(agv)
            if agv in self.ready_to_start_list:
                self.ready_to_start_list.remove(agv)
            distance = AGV.calculate_distance(agv.current_location, yard_block.cp)
            self.time_span = distance / agv.speed
            self.schedule(lambda: self.complete(agv), timedelta(seconds=self.time_span))
            self.emit_on_start(agv)

    class HoldingAtYard(BaseActivity):
        """Represents the HoldingAtYard state for AGV."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="HoldingAtYard", debug_mode=debug_mode, seed=seed)
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)
            self.containers_pending = []

        def attempt_to_finish(self, agv):
            """Attempt to finish the HoldingAtYard state."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.AttemptToFinish({agv})")
            if agv in self.completed_list and self.need_ext_try_finish and agv in self.ready_to_finish_list:
                self.finish(agv)
            elif agv in self.completed_list and self.need_ext_try_finish and agv not in self.ready_to_finish_list and len(self.containers_pending) >0:
                if agv.loaded_container in self.containers_pending:
                    self.containers_pending.remove(agv.loaded_container)
                    agv.loaded_container.current_location = agv.targeted_yb.cp
                    agv.current_location = agv.targeted_yb.cp
                    agv.loaded_container = None
                    agv.targeted_yb = None
                    agv.in_discharging = False
                    self.ready_to_finish_list.append(agv)
                    self.finish(agv)
                else:
                    print(f"Error: {self.clock_time}  {self.activity_name}.AttemptToFinish({agv}): we don't find the determined container for unloading")


        def try_finish(self, obj):
            """Try to finish HoldingAtYard."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None            
            if container:
                self.containers_pending.append(container)
                agv = next((a for a in self.completed_list if a.loaded_container == container), None)
                if agv:
                    self.containers_pending.remove(container)
                    container.block_stacked = agv.targeted_yb
                    agv.current_location = agv.targeted_yb.cp
                    agv.loaded_container = None
                    agv.targeted_yb = None
                    agv.in_discharging = False
                    self.ready_to_finish_list.append(agv)
                    self.attempt_to_finish(agv)

    class DeliveringToQuaySide(BaseActivity):
        """Represents the DeliveringToQuaySide state for AGV."""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="DeliveringToQuaySide", debug_mode=debug_mode, seed=seed)
            self.yc_pending_list = []
            self.need_ext_try_start = True
    
        def attempt_to_start(self):
            """Attempt to start the first eligible AGV in the pending list."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.AttemptToStart()")
    
            if self.pending_list and self.capacity_occupied < self.capacity:
                for i, agv in enumerate(self.pending_list):
                    if agv in self.ready_to_start_list:
                        self.start(agv)
                        break
                    elif agv not in self.ready_to_start_list and any(
                        yc for yc in self.yc_pending_list if yc.held_container == agv.loaded_container
                    ):
                        yc = next(
                            yc for yc in self.yc_pending_list if yc.held_container == agv.loaded_container
                        )
                        self.yc_pending_list.remove(yc)
                        self.start(agv)
                        break
    
        def try_start(self, obj):
            """Handle an external request to start."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.TryStart({obj})")
            from port_simulation.entity.yc import YC
            yc = obj if isinstance(obj, YC) else None
            if yc:
                self.yc_pending_list.append(yc)
                agv = next(
                    (a for a in self.pending_list if a.loaded_container == yc.held_container), None
                )
                if agv:
                    self.yc_pending_list.remove(yc)
                    self.ready_to_start_list.append(agv)
                    self.attempt_to_start()
    
        def start(self, agv):
            """Start the DeliveringToQuaySide process."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.Start({agv})")
            self.hour_counter.observe_change(1)
            self.processing_list.append(agv)
            self.pending_list.remove(agv)
            if agv in self.ready_to_start_list:
                self.ready_to_start_list.remove(agv)
            distance = AGV.calculate_distance(agv.current_location, agv.targeted_qc.cp)
            self.time_span = timedelta(seconds=distance / agv.speed)
            self.schedule(lambda: self.complete(agv), self.time_span)
            self.emit_on_start(agv)


    class HoldingAtQuaySide(BaseActivity):
        """Represents the HoldingAtQuaySide state for AGV."""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="HoldingAtQuaySide", debug_mode=debug_mode, seed=seed)
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)
            self.containers_pending = []
    
        def start(self, agv):
            """Start the HoldingAtQuaySide process."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.Start({agv})")
            self.hour_counter.observe_change(1)
            self.processing_list.append(agv)
            self.pending_list.remove(agv)
            if agv in self.ready_to_start_list:
                self.ready_to_start_list.remove(agv)
            self.schedule(lambda: self.complete(agv), self.time_span)
            self.emit_on_start(agv)
    
        def attempt_to_finish(self, agv):
            """Attempt to finish the HoldingAtQuaySide state."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.AttemptToFinish({agv})")
            if agv in self.completed_list and self.need_ext_try_finish and agv in self.ready_to_finish_list:
                self.finish(agv)
            elif agv in self.completed_list and self.need_ext_try_finish and agv not in self.ready_to_finish_list:
                if agv.loaded_container in self.containers_pending:
                    self.containers_pending.remove(agv.loaded_container)
                    # Update AGV's dynamics
                    agv.current_location = agv.targeted_qc.cp
                    agv.loaded_container = None
                    agv.targeted_qc = None
                    agv.in_discharging = False
                    self.ready_to_finish_list.append(agv)
                    self.finish(agv)
    
        def try_finish(self, obj):
            """Try to finish HoldingAtQuaySide."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if container:
                self.containers_pending.append(container)
                agv = next((a for a in self.completed_list if a.loaded_container == container), None)
                if agv:
                    self.containers_pending.remove(container)
                    # Update AGV's dynamics
                    agv.current_location = agv.targeted_qc.cp
                    agv.loaded_container = None
                    agv.targeted_qc = None
                    agv.in_discharging = False
                    self.ready_to_finish_list.append(agv)
                    self.attempt_to_finish(agv)
