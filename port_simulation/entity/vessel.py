from datetime import datetime, timedelta
from collections import defaultdict
from activity.base_activity import BaseActivity



class Vessel:
    """Class representing a vessel in the port simulation."""

    def __init__(self, id=None, discharging_containers_information=None, loading_containers_information=None, week=0):
        self.week=week;
        self.id = id
        self.already_allocated_qc_count = 0
        self.required_qc_count = 3
        self.allocated_berth = None
        self.allocated_qcs = []
        self.used_qc_line = None
        self.discharging_containers_information = discharging_containers_information
        self.loading_containers_information = loading_containers_information
        self.arrival_time = None
        self.start_berthing_time = None
        self.departure_time = None
        self.service_time = None

    def __str__(self):
        return f"Vessel[{self.id}]"


    class Waiting(BaseActivity):
        """Represents the Waiting state for a vessel."""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Waiting", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)
    
        def start(self, vessel):
            """Start the Waiting process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.Start({vessel})")
            _clock_time = self.clock_time
            vessel.arrival_time = _clock_time
            self.hour_counter.observe_change(1)
            self.processing_list.append(vessel)
            self.pending_list.remove(vessel)
            if vessel in self.ready_to_start_list:
                self.ready_to_start_list.remove(vessel)
            self.schedule(lambda: self.complete(vessel), self.time_span)
            self.emit_on_start(vessel)
            #print(f"{self.clock_time}, week: {vessel.week}, id: {vessel.id}, containers: {sum(vessel.discharging_containers_information.values())}")


    class Berthing(BaseActivity):
        """Represents the Berthing state for a vessel."""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Berthing", debug_mode=debug_mode, seed=seed)
            self.need_ext_try_start = True
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)
            self.if_use_rl = False

            self.strategy_maker = None
    
        def request_to_start(self, vessel):
            """Request to start the berthing process."""
            self.pending_list.append(vessel)
            self.schedule(self.attempt_to_start, timedelta(microseconds=1))
            #print(f"{self.clock_time} {self.activity_name}.RequestToStart({vessel})")
    
        def try_start(self, obj):
            """Handle external resources for starting."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryStart({obj})")
            from port_simulation.entity.berth import Berth
            from port_simulation.entity.qc import QC
            berth = obj if isinstance(obj, Berth) else None
            qc = obj if isinstance(obj, QC) else None
    
            if berth:
                vessel = next((v for v in self.pending_list if v.allocated_berth == berth), None)
                if vessel and len(vessel.allocated_qcs) == vessel.required_qc_count and vessel.allocated_berth:
                    self.ready_to_start_list.append(vessel)
                    self.attempt_to_start()
            elif qc:
                vessel = next((v for v in self.pending_list if v == qc.served_vessel), None)
                if not vessel:
                    print(f"Error: Vessel not found for QC {qc}")
                    return
                vessel.allocated_qcs.append(qc)
                if len(vessel.allocated_qcs) == vessel.required_qc_count and vessel.allocated_berth:
                    self.ready_to_start_list.append(vessel)
                    self.attempt_to_start()
    
        def start(self, vessel):
            """Start the berthing process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.Start({vessel})")
            vessel.start_berthing_time = self.clock_time
            self.hour_counter.observe_change(1)
            self.processing_list.append(vessel)
            self.pending_list.remove(vessel)
            if vessel in self.ready_to_start_list:
                self.ready_to_start_list.remove(vessel)
            self.schedule(lambda: self.complete(vessel), self.time_span)
            self.emit_on_start(vessel)
    
        def try_finish(self, obj):
            """Handle external request to finish the berthing process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.qc_line import QCLine
            qc_line = obj if isinstance(obj, QCLine) else None
            if not qc_line:
                return
            for vessel in self.completed_list:
                if qc_line.served_vessel == vessel:
                    self.ready_to_finish_list.append(vessel)
                    self.attempt_to_finish(vessel)
                    break
                
        def depart(self, vessel):
            """Removes a task from the system and attempts to start new tasks."""
            if vessel in self.ready_to_depart_list:
                if self.debug_mode:
                    print(f"{self.clock_time}  {self.activity_name}.Depart({vessel})")
                self.hour_counter.observe_change(-1)
                self.ready_to_depart_list.remove(vessel)
                vessel.departure_time = self.clock_time
                vessel.service_time = (vessel.departure_time - vessel.start_berthing_time).total_seconds() / 3600
                #print(self.strategy_maker.reinforcing_learning)
                #print(f"{vessel}: {vessel.arrival_time}, {vessel.start_berthing_time}, {vessel.departure_time}")
                if self.if_use_rl is True:
                    self.strategy_maker.get_reward_and_update(vessel)
                self.attempt_to_start()
