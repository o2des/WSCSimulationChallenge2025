# File path: port_simulation/entity/container.py

from datetime import timedelta
from port_simulation.entity.control_point import ControlPoint
from activity.base_activity import BaseActivity
from o2despy.action import Action
from o2despy.entity import Entity

class Container:
    """Represents a container in the port simulation."""

    def __init__(self, id=None, discharging_vessel=None, discharging_vessel_id = None, loading_vessel_id = None,
                 arrival_time = None, in_discharging=True, week=0):
        self.week = week
        self.discharging_vessel = discharging_vessel
        self.loading_vessel = None
        self.discharging_vessel_id = discharging_vessel_id
        self.loading_vessel_id = loading_vessel_id
        self.block_stacked = None
        self.target_qc = None
        self.current_location = None
        self.arrival_time = arrival_time
        self.agv_taken = None
        self.in_discharging = in_discharging
        self.id = id

    def __str__(self):
        return f"Container[{self.id}]"

    class BeingDischarged(BaseActivity):
        """Represents the BeingDischarged state for a container."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingDischarged", debug_mode=debug_mode, seed=seed)
            self.on_request_to_start = Action(Entity)
            self.discharging = 0
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_start = True
            self.need_ext_try_finish = True

        def generate_containers(self, qc_line):
            """Generate containers based on the QCLine."""
            served_vessel = qc_line.served_vessel
            id_counter = 0
            for dest, count in served_vessel.discharging_containers_information.items():
                for _ in range(count):
                    container_id = f"{served_vessel.id}, {served_vessel.arrival_time}, {id_counter}"
                    container = Container(
                        id=container_id,
                        discharging_vessel=served_vessel,
                        discharging_vessel_id=served_vessel.id,
                        loading_vessel_id=dest,
                        arrival_time=served_vessel.arrival_time,
                        in_discharging=True,
                        week=served_vessel.week
                    )
                    self.on_request_to_start.invoke(container)
                    self.request_to_start(container)
                    id_counter += 1

        def try_start(self, obj):
            """Try to start the discharging process."""
            from port_simulation.entity.qc import QC
            qc = obj if isinstance(obj, QC) else None
            if qc:
                chosen_container = next((con for con in self.pending_list if con == qc.held_container), None)
                if chosen_container:
                    self.ready_to_start_list.append(chosen_container)
                    chosen_container.current_location = qc.cp
                    self.attempt_to_start()
                else:
                    print(f"Error: No matching container for QC {qc}.")

        def try_finish(self, obj):
            """Try to finish the discharging process."""
            from port_simulation.entity.qc import QC
            qc = obj if isinstance(obj, QC) else None
            if qc:
                chosen_container = next((con for con in self.completed_list if con == qc.held_container), None)
                if chosen_container:
                    self.ready_to_finish_list.append(chosen_container)
                    self.attempt_to_finish(chosen_container)
                    self.discharging += 1
                else:
                    print(f"Error: No matching container for QC {qc}.")

    class TransportingToYard(BaseActivity):
        """Represents the TransportingToYard state for a container."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="TransportingToYard", debug_mode=debug_mode, seed=seed)
            self.agv_pending_list = []
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_start = True
            self.need_ext_try_finish = True

        def try_start(self, obj):
            """Try to start the transport to yard process."""
            from port_simulation.entity.agv import AGV
            agv = obj if isinstance(obj, AGV) else None
            if agv:
                container = next((con for con in self.pending_list if con == agv.loaded_container), None)
                if container:
                    self.ready_to_start_list.append(container)
                    self.attempt_to_start()
                else:
                    print(f"Error: No matching container for AGV {agv}.")

        def attempt_to_finish(self, container):
            """Attempt to finish the transport to yard process."""
            if container in self.completed_list and container in self.ready_to_finish_list:
                self.finish(container)
            elif container in self.completed_list and container not in self.ready_to_finish_list:
                agv = next((a for a in self.agv_pending_list if a.loaded_container == container), None)
                if agv:
                    self.agv_pending_list.remove(agv)
                    self.ready_to_finish_list.append(container)
                    self.finish(container)

        def try_finish(self, obj):
            """Try to finish the transport to yard process."""
            from port_simulation.entity.agv import AGV
            agv = obj if isinstance(obj, AGV) else None
            if agv:
                self.agv_pending_list.append(agv)
                container = next((con for con in self.completed_list if con == agv.loaded_container), None)
                if container:
                    self.agv_pending_list.remove(agv)
                    self.ready_to_finish_list.append(container)
                    self.attempt_to_finish(container)

    class BeingStacked(BaseActivity):
        """Represents the BeingStacked state for a container."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingStacked", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_start = True
            self.need_ext_try_finish = True

        def try_start(self, obj):
            """Try to start stacking."""
            from port_simulation.entity.yc import YC
            yc = obj if isinstance(obj, YC) else None
            if yc:
                container = next((con for con in self.pending_list if con == yc.held_container), None)
                if container:
                    self.ready_to_start_list.append(container)
                    self.attempt_to_start()
                else:
                    print(f"Error: No matching container for YC {yc}.")

        def try_finish(self, obj):
            """Try to finish stacking."""
            from port_simulation.entity.yc import YC
            yc = obj if isinstance(obj, YC) else None
            if yc:
                container = next((con for con in self.completed_list if con == yc.held_container), None)
                if container:
                    self.ready_to_finish_list.append(container)
                    self.attempt_to_finish(container)
                    
        def depart(self, container):
            """Depart after stacking."""
            if container in self.ready_to_depart_list:
                if self.debug_mode:
                    print(f"{self.clock_time} {self.activity_name}.Depart({container})")
                self.hour_counter.observe_change(-1)
                container.in_discharging = False
                container.block_stacked.stacking_container(container)
                self.ready_to_depart_list.remove(container)
                self.attempt_to_start()


    class Dwelling(BaseActivity):
        """Represents the Dwelling state for a container."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Dwelling", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_finish = True

        def try_finish(self, obj):
            """Try to finish the dwelling process."""
            from port_simulation.entity.qc_line import QCLine
            qc_line = obj if isinstance(obj, QCLine) else None
            if qc_line and qc_line.loading_containers_information:
                for origin, quantity in qc_line.loading_containers_information.items():
                    #print(f"{self.clock_time}|||||||{quantity} from {origin} to {qc_line.served_vessel.id}")
                    for i in range(quantity):
                        stocked_container = next(
                            (con for con in self.completed_list if con.loading_vessel_id == qc_line.served_vessel.id
                             and con.week < qc_line.served_vessel.week and con.discharging_vessel_id == origin),
                            None
                        )
                        if stocked_container:
                            stocked_container.block_stacked.unstacking_container(stocked_container)
                            self.ready_to_finish_list.append(stocked_container)
                            self.attempt_to_finish(stocked_container)
                        else:
                            print(f"{self.clock_time} Error: No containers from {origin} to {qc_line.served_vessel.id}.")

    class BeingUnstacked(BaseActivity):
        """Represents the BeingUnstacked state for a container."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingUnstacked", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_start = True
            self.need_ext_try_finish = True

        def try_start(self, obj):
            """Try to start unstacking."""
            from port_simulation.entity.yc import YC
            yc = obj if isinstance(obj, YC) else None
            if yc:
                container = next((con for con in self.pending_list if con == yc.held_container), None)
                if container:
                    self.ready_to_start_list.append(container)
                    self.attempt_to_start()
                else:
                    print(f"Error: No matching container for YC {yc}.")

        def try_finish(self, obj):
            """Try to finish unstacking."""
            from port_simulation.entity.yc import YC
            yc = obj if isinstance(obj, YC) else None
            if yc:
                container = next((con for con in self.completed_list if con == yc.held_container), None)
                if container:
                    self.ready_to_finish_list.append(container)
                    self.attempt_to_finish(container)

    class TransportingToQuaySide(BaseActivity):
        """Represents the TransportingToQuaySide state for a container."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="TransportingToQuaySide", debug_mode=debug_mode, seed=seed)
            self.agv_pending_list = []
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_start = True
            self.need_ext_try_finish = True

        def try_start(self, obj):
            """Try to start the transport to quay side process."""
            from port_simulation.entity.agv import AGV
            agv = obj if isinstance(obj, AGV) else None
            if agv:
                container = next((con for con in self.pending_list if con == agv.loaded_container), None)
                if container:
                    self.ready_to_start_list.append(container)
                    self.attempt_to_start()
                else:
                    print(f"Error: No matching container for AGV {agv}.")

        def attempt_to_finish(self, container):
            """Attempt to finish the transport to quay side process."""
            if container in self.completed_list and container in self.ready_to_finish_list:
                self.finish(container)
            elif container in self.completed_list and container not in self.ready_to_finish_list:
                agv = next((a for a in self.agv_pending_list if a.loaded_container == container), None)
                if agv:
                    self.agv_pending_list.remove(agv)
                    self.ready_to_finish_list.append(container)
                    self.finish(container)

        def try_finish(self, obj):
            """Try to finish the transport to quay side process."""
            from port_simulation.entity.agv import AGV
            agv = obj if isinstance(obj, AGV) else None
            if agv:
                self.agv_pending_list.append(agv)
                container = next((con for con in self.completed_list if con == agv.loaded_container), None)
                if container:
                    self.agv_pending_list.remove(agv)
                    self.ready_to_finish_list.append(container)
                    self.attempt_to_finish(container)

    class BeingLoaded(BaseActivity):
        """Represents the BeingLoaded state for a container."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="BeingLoaded", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)
            self.need_ext_try_start = True
            self.need_ext_try_finish = True
            self.loading = 0

        def try_start(self, obj):
            """Try to start the loading process."""
            from port_simulation.entity.qc import QC
            qc = obj if isinstance(obj, QC) else None
            if qc:
                held_container = next((con for con in self.pending_list if con == qc.held_container), None)
                if held_container:
                    self.ready_to_start_list.append(held_container)
                else:
                    print(f"Error: No containers served for {qc.served_vessel}.")
                self.attempt_to_start()

        def try_finish(self, obj):
            """Try to finish the loading process."""
            from port_simulation.entity.qc import QC
            qc = obj if isinstance(obj, QC) else None
            if qc:
                held_container = next((con for con in self.completed_list if con == qc.held_container), None)
                if held_container:
                    self.ready_to_finish_list.append(held_container)
                    self.attempt_to_finish(held_container)
                    self.loading += 1
                else:
                    print(f"Error: No containers served for {qc.served_vessel}.")