# File path: port_simulation/entity/berth.py

from datetime import timedelta
from activity.base_activity import BaseActivity


class Berth:
    """Represents a Berth in the port simulation."""

    def __init__(self, id=None, equipped_qcs = None):
        self.id = id
        self.current_work_qc = 0
        self.berthed_vessel = None
        self.equipped_qcs = equipped_qcs

    def __str__(self):
        return f"Berth[{self.id}]"


    class BeingIdle(BaseActivity):
        """Represents the BeingIdle state for a Berth."""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingIdle", debug_mode=debug_mode, seed=seed)
            self.vessel_pending_list = []
            from strategy_making.default import Default
            self.strategy_maker = None
            self.default_maker = Default()
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)
    
        def attempt_to_finish(self, berth):
            """Attempt to finish the BeingIdle state."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.AttemptToFinish({berth})")
    
            if berth in self.completed_list and self.need_ext_try_finish and berth in self.ready_to_finish_list:
                self.finish(berth)
            elif (berth in self.completed_list and self.need_ext_try_finish and berth not in self.ready_to_finish_list
                  and self.vessel_pending_list):
                (allocated_berth, allocated_vessel) = self.strategy_maker.customeized_allocated_berth(self.vessel_pending_list)
                
                if(allocated_berth is None and allocated_vessel is None):
                    (allocated_berth, allocated_vessel) = self.default_maker.allocated_berth(self.vessel_pending_list)
    
                if (allocated_berth and allocated_berth in self.completed_list) and (allocated_vessel and allocated_vessel in self.vessel_pending_list):
                    allocated_berth.berthed_vessel = allocated_vessel
                    allocated_vessel.allocated_berth = allocated_berth
                    self.vessel_pending_list.remove(allocated_vessel)
                    self.finish(allocated_berth)
    
        def try_finish(self, obj):
            """Try to finish BeingIdle state."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.vessel import Vessel
            vessel = obj if isinstance(obj, Vessel) else None
            if vessel:
                self.vessel_pending_list.append(vessel)
    
            num_of_try_finish = min(len(self.completed_list), len(self.vessel_pending_list))
            tmp_berths = []                              
                
            for _ in range(num_of_try_finish):
                (allocated_berth, allocated_vessel) = self.strategy_maker.customeized_allocated_berth(self.vessel_pending_list)
                
                if(allocated_berth is None and allocated_vessel is None):
                    (allocated_berth, allocated_vessel) = self.default_maker.allocated_berth(self.vessel_pending_list)
                                  
                if (allocated_berth and allocated_berth in self.completed_list) and (allocated_vessel and allocated_vessel in self.vessel_pending_list):
                    allocated_berth.berthed_vessel = allocated_vessel
                    allocated_vessel.allocated_berth = allocated_berth
                    tmp_berths.append(allocated_berth)
                    self.vessel_pending_list.remove(allocated_vessel)
                    self.ready_to_finish_list.append(allocated_berth)
                else:
                    break
    
            for berth in tmp_berths:
                self.attempt_to_finish(berth)
    
    
    class BeingOccupied(BaseActivity):
        """Represents the BeingOccupied state for a Berth."""
    
        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingOccupied", debug_mode=debug_mode, seed=seed)
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)
    
        def try_finish(self, obj):
            """Try to finish the BeingOccupied state."""
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.vessel import Vessel
            vessel = obj if isinstance(obj, Vessel) else None
            if not vessel:
                return
    
            allocated_berth = next((b for b in self.completed_list if b.berthed_vessel == vessel), None)
    
            if allocated_berth:
                allocated_berth.berthed_vessel = None
                self.ready_to_finish_list.append(allocated_berth)
                self.attempt_to_finish(allocated_berth)
            else:
                print(f"Error: {self.clock_time}  {self.activity_name}.TryFinish({obj}): "
                      f"could not find the allocated berth for releasing.")
