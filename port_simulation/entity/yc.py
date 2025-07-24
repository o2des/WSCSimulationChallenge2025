# File path: port_simulation/entity/yc.py

from datetime import timedelta
from collections import defaultdict
from activity.base_activity import BaseActivity


class YC:
    """Represents a Yard Crane (YC) in the port simulation."""

    def __init__(self, id=None, served_block=None, cp = None):
        self.id = id
        self.cp = cp
        self.served_block = served_block
        self.held_container = None

    def __str__(self):
        return f"YC[{self.id}]"

    class Repositioning(BaseActivity):
        """Represents the Repositioning state for a YC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Repositioning", debug_mode=debug_mode, seed=seed)
            self.container_pending_list = []
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)

        def re_being_idle_yc(self, yc):
            """Reset the YC's held container."""
            yc.held_container = None

        def attempt_to_finish(self, yc):
            """Attempt to finish the repositioning process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.AttemptToFinish({yc})")
            if yc in self.completed_list and self.need_ext_try_finish and yc in self.ready_to_finish_list:
                self.finish(yc)
            elif yc in self.completed_list and self.need_ext_try_finish and yc not in self.ready_to_finish_list:
                container = next(
                    (con for con in self.container_pending_list if con.block_stacked == yc.served_block), None
                )
                if container:
                    self.container_pending_list.remove(container)
                    yc.held_container = container
                    self.ready_to_finish_list.append(yc)
                    self.finish(yc)

        def try_finish(self, obj):
            """Try to finish the repositioning process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            agv = obj if hasattr(obj, "loaded_container") and obj.loaded_container else None

            if container:
                self.container_pending_list.append(container)
            elif agv and not agv.loaded_container.in_discharging:
                container = agv.loaded_container
                self.container_pending_list.append(container)
            else:
                return

            yc = next((y for y in self.completed_list if y.served_block == container.block_stacked), None)
            priority_container = next(
                (con for con in self.container_pending_list if con.block_stacked == container.block_stacked and not con.in_discharging),
                None
            )
            container = priority_container or container
            if yc:
                self.container_pending_list.remove(container)
                yc.held_container = container
                self.ready_to_finish_list.append(yc)
                self.attempt_to_finish(yc)

    class Picking(BaseActivity):
        """Represents the Picking state for a YC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Picking", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=0)

    class Stacking(BaseActivity):
        """Represents the Stacking state for a YC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Stacking", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=90)

    class Unstacking(BaseActivity):
        """Represents the Unstacking state for a YC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="Unstacking", debug_mode=debug_mode, seed=seed)
            self.time_span = timedelta(seconds=90)

    class HoldingOnUnstacking(BaseActivity):
        """Represents the HoldingOnUnstacking state for a YC."""

        def __init__(self, debug_mode=False, seed=0):
            super().__init__(name="HoldingOnUnstacking", debug_mode=debug_mode, seed=seed)
            self.container_pending_list = []
            self.need_ext_try_finish = True
            self.time_span = timedelta(seconds=0)

        def attempt_to_finish(self, yc):
            """Attempt to finish the holding on unstacking process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.AttemptToFinish({yc})")
            if yc in self.completed_list and self.need_ext_try_finish and yc in self.ready_to_finish_list:
                self.finish(yc)
            elif yc in self.completed_list and self.need_ext_try_finish and yc not in self.ready_to_finish_list:
                container = next((con for con in self.container_pending_list if con == yc.held_container), None)
                if container:
                    self.container_pending_list.remove(container)
                    self.ready_to_finish_list.append(yc)
                    self.finish(yc)

        def try_finish(self, obj):
            """Try to finish the holding on unstacking process."""
            if self.debug_mode:
                print(f"{self.clock_time} {self.activity_name}.TryFinish({obj})")
            from port_simulation.entity.container import Container
            container = obj if isinstance(obj, Container) else None
            if not container:
                return
            self.container_pending_list.append(container)
            yc = next((y for y in self.completed_list if y.held_container == container), None)
            if yc:
                self.container_pending_list.remove(container)
                self.ready_to_finish_list.append(yc)
                self.attempt_to_finish(yc)


class YardBlock:
    """Represents a Yard Block in the port simulation."""

    def __init__(self, id=None, capacity=0, cp = None):
        self.equipped_yc = None
        self.id = id
        self.stacked_containers = []
        self.reserved_slots = 0
        self.capacity = capacity
        self.cp = cp

    def reserve_slot(self):
        """Reserve a slot in the yard block."""
        if len(self.stacked_containers) + self.reserved_slots < self.capacity:
            self.reserved_slots += 1
        else:
            print(f"Failed reserving slot at yardblock: {self.id}, "
                  f"current status: stacked container number {len(self.stacked_containers)}, "
                  f"ReservedSlots: {self.reserved_slots}")

    def stacking_container(self, container):
        """Stack a container in the yard block."""
        self.reserved_slots -= 1
        self.stacked_containers.append(container)

    def unstacking_container(self, container):
        """Unstack a container from the yard block."""
        self.stacked_containers.remove(container)
