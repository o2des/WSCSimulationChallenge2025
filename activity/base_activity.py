from datetime import timedelta
from functools import partial
from o2despy.sandbox import Sandbox
from o2despy.hour_counter import HourCounter
from o2despy.action import Action
from o2despy.entity import Entity


class BaseActivity(Sandbox):
    """BaseActivity is a generic activity simulation class with customizable behavior."""

    BASE_ACTIVITY_DEFAULT_TIMESPAN = timedelta(seconds=1)
    BASE_ACTIVITY_DEFAULT_CAPACITY = float("inf")  # Infinity for unbounded capacity

    def __init__(self, name=None, debug_mode=False, seed=0):
        super().__init__(seed=seed)
        self.activity_name = name or self.__class__.__name__
        self.time_span = self.BASE_ACTIVITY_DEFAULT_TIMESPAN
        self.capacity = self.BASE_ACTIVITY_DEFAULT_CAPACITY
        self.debug_mode = debug_mode
        self.need_ext_try_start = False
        self.need_ext_try_finish = False

        # Dynamics
        self.pending_list = []
        self.ready_to_start_list = []
        self.processing_list = []
        self.completed_list = []
        self.ready_to_finish_list = []
        self.ready_to_depart_list = []
        self.hour_counter = self.add_hour_counter()

        # Events
        self.on_ready_to_depart = Action(Entity)
        self.on_start = Action(Entity)

    @property
    def capacity_occupied(self):
        """Total number of tasks in various states occupying the capacity."""
        return (
            len(self.processing_list)
            + len(self.completed_list)
            + len(self.ready_to_depart_list)
        )

    def request_to_start(self, load):
        """Requests to add a load to the pending list and schedules an attempt to start."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.RequestToStart({load})")
        self.pending_list.append(load)
        self.schedule(self.attempt_to_start, timedelta(microseconds=1))

    def try_start(self, obj):
        """Checks external conditions for starting a task."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.TryStart({obj})")
        condition = isinstance(obj, dict)  # Adjust condition logic as needed
        load = self.pending_list[0] if self.pending_list else None
        if condition and load:
            self.ready_to_start_list.append(load)
        self.attempt_to_start()

    def attempt_to_start(self):
        """Attempts to start a task from the pending list."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.AttemptToStart()")
        if self.pending_list and self.capacity_occupied < self.capacity:
            if not self.need_ext_try_start:
                self.start(self.pending_list[0])
            else:
                for load in self.pending_list:
                    if load in self.ready_to_start_list:
                        self.start(load)
                        break

    def start(self, load):
        """Moves a task to the processing list and schedules its completion."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.Start({load})")
        self.hour_counter.observe_change(1)
        self.processing_list.append(load)
        self.pending_list.remove(load)
        if load in self.ready_to_start_list:
            self.ready_to_start_list.remove(load)
        self.schedule(self.complete, self.time_span, load=load)
        self.emit_on_start(load)

    def complete(self, load):
        """Completes a task and schedules an attempt to finish."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.Complete({load})")
        self.completed_list.append(load)
        self.processing_list.remove(load)
        self.attempt_to_finish(load)

    def try_finish(self, obj):
        """Checks external conditions for finishing a task."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.TryFinish({obj})")
        condition = isinstance(obj, dict)  # Adjust condition logic as needed
        load = self.completed_list[0] if self.completed_list else None
        if condition and load:
            self.ready_to_finish_list.append(load)
        self.attempt_to_finish(load)

    def attempt_to_finish(self, load):
        """Attempts to finish a completed task."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.AttemptToFinish({load})")
        if load in self.completed_list and (
            not self.need_ext_try_finish or load in self.ready_to_finish_list
        ):
            self.finish(load)

    def finish(self, load):
        """Marks a task as ready to depart."""
        if self.debug_mode:
            print(f"{self.clock_time}  {self.activity_name}.Finish({load})")
        self.ready_to_depart_list.append(load)
        self.completed_list.remove(load)
        if load in self.ready_to_finish_list:
            self.ready_to_finish_list.remove(load)
        self.emit_on_ready_to_depart(load)

    def depart(self, load):
        """Removes a task from the system and attempts to start new tasks."""
        if load in self.ready_to_depart_list:
            if self.debug_mode:
                print(f"{self.clock_time}  {self.activity_name}.Depart({load})")
            self.hour_counter.observe_change(-1)
            self.ready_to_depart_list.remove(load)
            self.attempt_to_start()

    def emit_on_start(self, load):
        """Triggers the on_start event."""
        self.on_start.invoke(load)

    def emit_on_ready_to_depart(self, load):
        """Triggers the on_ready_to_depart event."""
        self.on_ready_to_depart.invoke(load)

    # Flow Methods
    def flow_to(self, next_activity):
        """ Connects this activity to the next activity in the flow. """
        self.on_ready_to_depart += next_activity.request_to_start
        next_activity.on_start += self.depart
        return next_activity

    def flow_to_branch(self, next_activity, condition):
        """ Connects this activity to a branch with a condition. """
        self.on_ready_to_depart += lambda load: next_activity.request_to_start(
            load
        ) if condition(load) else None
        next_activity.on_start += lambda load: self.depart(load) if condition(load) else None
        return next_activity

    def terminate(self):
        """ Terminates the activity by linking the depart action. """
        self.on_ready_to_depart += self.depart