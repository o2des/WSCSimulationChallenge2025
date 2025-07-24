# File path: port_simulation/entity/qc.py

from datetime import timedelta
from collections import defaultdict
from port_simulation.entity.control_point import ControlPoint
from activity.base_activity import BaseActivity


class QC:
    """Represents a QC (Quay Crane) in the port simulation."""

    def __init__(self, id=None, cp=None):
        self.id = id
        self.served_vessel = None
        self.located_berth = None
        self.held_container = None
        self.cp = cp

    def __str__(self):
        return f"QC[{self.id}]"

    class BeingIdle(BaseActivity):
        """Represents the BeingIdle state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingIdle", debug_mode=debug_mode, seed=seed)
            self.berth_pending_list = []
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)

        def re_being_idle_qc(self, qc):
            """Reset the QC's served vessel."""
            qc.served_vessel = None

        def attempt_to_finish(self, qc):
            """Attempt to finish the BeingIdle state."""
            if self.debug_mode:
                print(f"{self.clock_time} QC{self.activity_name}.AttemptToFinish({qc})")
            if qc in self.completed_list and self.need_ext_try_finish and qc in self.ready_to_finish_list:
                self.finish(qc)
            elif qc in self.completed_list and self.need_ext_try_finish and qc not in self.ready_to_finish_list and self.berth_pending_list:
                allocated_qcs = [q for q in self.completed_list if q.located_berth == self.berth_pending_list[0]]
                if allocated_qcs:
                    for allocated_qc in allocated_qcs:
                        self.berth_pending_list[0].berthed_vessel.already_allocated_qc_count += 1
                        allocated_qc.served_vessel = self.berth_pending_list[0].berthed_vessel
                        self.ready_to_finish_list.append(allocated_qc)
                        self.finish(allocated_qc)
                    if self.berth_pending_list[0].berthed_vessel.already_allocated_qc_count == self.berth_pending_list[0].berthed_vessel.required_qc_count:
                        self.berth_pending_list.pop(0)

        def try_finish(self, obj):
            """Handle the request to finish the BeingIdle state."""
            if self.debug_mode:
                print(f"{self.clock_time} QC{self.activity_name}.TryFinish({obj})")
        
            # Validate and ensure `obj` is a Berth
            from port_simulation.entity.berth import Berth
            berth = obj if isinstance(obj, Berth) else None
            if berth is None:
                return
        
            # Add the berth to the pending list
            self.berth_pending_list.append(berth)
        
            # Retrieve all QCs associated with the first berth in the pending list
            allocated_qcs = [qc for qc in self.completed_list if qc.located_berth == self.berth_pending_list[0]]
        
            if not allocated_qcs:
                if self.debug_mode:
                    print(f"No allocated QCs found for berth {self.berth_pending_list[0]}")
                return
        
            # Process each QC and update its state
            for allocated_qc in allocated_qcs:
                self.berth_pending_list[0].berthed_vessel.already_allocated_qc_count += 1
                allocated_qc.served_vessel = self.berth_pending_list[0].berthed_vessel
                self.ready_to_finish_list.append(allocated_qc)
                self.attempt_to_finish(allocated_qc) 
            if self.berth_pending_list[0].berthed_vessel.already_allocated_qc_count == self.berth_pending_list[0].berthed_vessel.required_qc_count:
                self.berth_pending_list.pop(0)


    class SettingUp(BaseActivity):
        """Represents the SettingUp state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="SettingUp", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=1500)

    class RestoringToDischarge(BaseActivity):
        """Represents the RestoringToDischarge state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="RestoringToDischarge", debug_mode=debug_mode, seed=seed)
            self.container_pending_list = []
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=35)

        def attempt_to_finish(self, qc):
            """Attempt to finish the restoring to discharge process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.AttemptToFinish({qc})")
            if qc in self.completed_list and self.need_ext_try_finish and qc in self.ready_to_finish_list:
                self.finish(qc)
            elif qc in self.completed_list and self.need_ext_try_finish and qc not in self.ready_to_finish_list:
                container = next(
                    (con for con in self.container_pending_list if con.discharging_vessel_id == qc.served_vessel.id and con.week == qc.served_vessel.week),
                    None
                )
                if container:
                    qc.served_vessel.discharging_containers_information[container.loading_vessel_id] -= 1
                    qc.held_container = container
                    self.container_pending_list.remove(container)
                    self.ready_to_finish_list.append(qc)
                    self.finish(qc)

        def try_finish(self, obj):
            """Try to finish the restoring to discharge process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if not container:
                return
            self.container_pending_list.append(container)
            qc = next(
                (q for q in self.completed_list if q.served_vessel.id == container.discharging_vessel_id and q.served_vessel.week == container.week),
                None
            )
            if qc:
                qc.served_vessel.discharging_containers_information[container.loading_vessel_id] -= 1
                qc.held_container = container
                self.container_pending_list.remove(container)
                self.ready_to_finish_list.append(qc)
                self.attempt_to_finish(qc)

    class Discharging(BaseActivity):
        """Represents the Discharging state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Discharging", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=75)

    class HoldingOnDischarging(BaseActivity):
        """Represents the HoldingOnDischarging state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="HoldingOnDischarging", debug_mode=debug_mode, seed=seed)
            self.container_pending_list = []
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)

        def attempt_to_finish(self, qc):
            """Attempt to finish the holding on discharging process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.AttemptToFinish({qc})")
            if qc in self.completed_list and self.need_ext_try_finish and qc in self.ready_to_finish_list:
                self.finish(qc)
            elif qc in self.completed_list and self.need_ext_try_finish and qc not in self.ready_to_finish_list:
                container = next((con for con in self.container_pending_list if con == qc.held_container), None)
                if container:
                    qc.held_container = None
                    self.container_pending_list.remove(container)
                    self.ready_to_finish_list.append(qc)
                    self.finish(qc)

        def try_finish(self, obj):
            """Try to finish the holding on discharging process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if not container:
                return
            self.container_pending_list.append(container)
            qc = next((q for q in self.completed_list if q.held_container == container), None)
            if qc:
                qc.held_container = None
                self.container_pending_list.remove(container)
                self.ready_to_finish_list.append(qc)
                self.attempt_to_finish(qc)

    class RestoringToLoad(BaseActivity):
        """Represents the RestoringToLoad state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="RestoringToLoad", debug_mode=debug_mode, seed=seed)
            self.container_pending_list = []
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=75)

        def attempt_to_finish(self, qc):
            """Attempt to finish restoring to load."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.AttemptToFinish({qc})")
            if qc in self.completed_list and self.need_ext_try_finish and qc in self.ready_to_finish_list:
                self.finish(qc)
            elif qc in self.completed_list and self.need_ext_try_finish and qc not in self.ready_to_finish_list:
                container = next(
                    (con for con in self.container_pending_list if con.target_qc.located_berth == qc.located_berth),
                    None
                )
                if container:
                    qc.served_vessel.loading_containers_information[container.loading_vessel_id] -= 1
                    # if(qc.served_vessel.loading_containers_information[container.loading_vessel_id] <0):
                    #     print(f"{self.clock_time}, {container.id}, {container.loading_vessel_id}, {qc.served_vessel.id}, {container.week}")
                    qc.held_container = container
                    self.container_pending_list.remove(container)
                    self.ready_to_finish_list.append(qc)
                    self.finish(qc)

        def try_finish(self, obj):
            """Try to finish restoring to load."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if not container:
                return
            self.container_pending_list.append(container)
            qc = next(
                (q for q in self.completed_list if container.target_qc.located_berth == q.located_berth),
                None
            )
            if qc:
                qc.served_vessel.loading_containers_information[container.loading_vessel_id] -= 1
                qc.held_container = container
                self.container_pending_list.remove(container)
                self.ready_to_finish_list.append(qc)
                self.attempt_to_finish(qc)

    class Loading(BaseActivity):
        """Represents the Loading state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Loading", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=35)

    class HoldingOnLoading(BaseActivity):
        """Represents the HoldingOnLoading state for a QC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="HoldingOnLoading", debug_mode=debug_mode, seed=seed)
            self.container_pending_list = []
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)

        def attempt_to_finish(self, qc):
            """Attempt to finish holding on loading."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.AttemptToFinish({qc})")
            if qc in self.completed_list and self.need_ext_try_finish and qc in self.ready_to_finish_list:
                self.finish(qc)
            elif qc in self.completed_list and self.need_ext_try_finish and qc not in self.ready_to_finish_list:
                container = next((con for con in self.container_pending_list if con == qc.held_container), None)
                if container:
                    qc.held_container = None
                    self.container_pending_list.remove(container)
                    self.ready_to_finish_list.append(qc)
                    self.finish(qc)

        def try_finish(self, obj):
            """Try to finish holding on loading."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if not container:
                return
            self.container_pending_list.append(container)
            qc = next((q for q in self.completed_list if q.held_container == container), None)
            if qc:
                qc.held_container = None
                self.container_pending_list.remove(container)
                self.ready_to_finish_list.append(qc)
                self.attempt_to_finish(qc)


