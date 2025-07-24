# File path: port_simulation/entity/qc_line.py

from datetime import datetime, timedelta
from collections import defaultdict
from activity.base_activity import BaseActivity


class QCLine:
    """Represents a QCLine in the port simulation."""

    def __init__(self, id=None):
        self.id = id
        self.served_vessel = None
        self.discharging_containers_information = defaultdict(int)
        self.loading_containers_information = defaultdict(int)

    def __str__(self):
        return f"QCLine[{self.id}]"

    class Discharging(BaseActivity):
        """Represents the Discharging state for a QCLine."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Discharging", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_finish = True

        def create_qc_line(self, vessel):
            """Create a QCLine for the given vessel."""
            _clock_time = self.clock_time
            qc_line = QCLine(id=f"({_clock_time},{vessel.id})")
            qc_line.served_vessel = vessel
            qc_line.discharging_containers_information = defaultdict(int, vessel.discharging_containers_information)
            if vessel.loading_containers_information:
                qc_line.loading_containers_information = defaultdict(int, vessel.loading_containers_information)
            self.request_to_start(qc_line)

        def try_finish(self, obj):
            """Try to finish the discharging process."""
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if not container:
                return

            worked_qc_line = next(
                (qc_line for qc_line in self.completed_list if qc_line.served_vessel.id == container.discharging_vessel_id),
                None
            )
            if worked_qc_line:
                worked_qc_line.discharging_containers_information[container.loading_vessel_id] -= 1
                all_containers_being_discharged = all(
                    count == 0 for count in worked_qc_line.discharging_containers_information.values()
                )

                if all_containers_being_discharged:
                    self.ready_to_finish_list.append(worked_qc_line)
                    self.attempt_to_finish(worked_qc_line)
                    worked_qc_line.discharging_containers_information.clear()
            else:
                print(f"Error: {self.clock_time} {self.activity_name}.TryFinish({obj}): "
                      f"QCLine not found for container {container.id}")

    class Loading(BaseActivity):
        """Represents the Loading state for a QCLine."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Loading", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_finish = True

        def attempt_to_finish(self, qc_line):
            """Attempt to finish the loading process."""
            if qc_line in self.completed_list and (
                not self.need_ext_try_finish
                or qc_line in self.ready_to_finish_list
                or not qc_line.loading_containers_information
            ):
                self.finish(qc_line)

        def try_finish(self, obj):
            """Try to finish the loading process."""
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if not container:
                return            
            worked_qc_line = next(
                (qc_line for qc_line in self.completed_list
                 if qc_line.served_vessel.id == container.loading_vessel_id
                 and qc_line.served_vessel.week > container.week),
                None
            )
            #print(f"{self.clock_time}, {worked_qc_line.id}, |container: {container.id}|, to {container.loading_vessel_id}")
            if worked_qc_line:
                worked_qc_line.loading_containers_information[container.discharging_vessel_id] -= 1
                all_containers_being_loaded = all(
                    count == 0 for count in worked_qc_line.loading_containers_information.values()
                )
                # if worked_qc_line.loading_containers_information[container.discharging_vessel_id] < 0:
                #     print(f"{self.clock_time}, {worked_qc_line.id}, |container: {container.id}|, to {container.loading_vessel_id}")
                
                if all_containers_being_loaded:
                    self.ready_to_finish_list.append(worked_qc_line)
                    self.attempt_to_finish(worked_qc_line)
                    worked_qc_line.loading_containers_information = None
            else:
                print(f"Error: {self.clock_time} {self.activity_name}.TryFinish({obj}): "
                      f"QCLine not found for container {container.id}")
