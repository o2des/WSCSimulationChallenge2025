import random
import csv
import os
from datetime import datetime, timedelta
from port_simulation.entity.berth import Berth
from port_simulation.entity.qc import QC
from port_simulation.entity.qc_line import QCLine
from port_simulation.entity.container import Container
from port_simulation.entity.vessel import Vessel
from port_simulation.entity.yc import YC
from port_simulation.entity.agv import AGV
from port_simulation.entity.yc import YardBlock
from port_simulation.entity.control_point import ControlPoint
from file_reader.file_reader import FileReader
from o2despy.sandbox import Sandbox

class PortSimModel(Sandbox):
    """Simulation model for port operations."""

    def __init__(self, number_of_agvs=0, start_time=None, containers_info_file_url=None, vessel_arrival_times_url=None):
        """Initialize the port simulation model."""
        super().__init__()
        self.discharging = 0
        self.loading = 0
        
        # Paths to configuration files
        self.containers_info_file_url = containers_info_file_url
        self.vessel_arrival_times_url = vessel_arrival_times_url
        self.qc_control_points_url = "conf/QC_controlpoint.csv"
        self.yc_control_points_url = "conf/YC_controlpoint.csv"

        # Static configuration
        self.number_of_berths = 4
        self.number_of_qcs_per_berth = 3
        self.number_of_agvs = number_of_agvs
        self.number_of_ycs = 0
        self.number_of_initial_agvs_per_qc = self.number_of_agvs // (self.number_of_berths * self.number_of_qcs_per_berth)
        self.number_of_qcs = self.number_of_berths * self.number_of_qcs_per_berth
        self.block_capacity = 1000
        self.running_weeks = 10
        self.warm_up_weeks = 2
        self.start_time = start_time

        self.random = None

        # Entities
        self.vessels = []
        self.berths = []
        self.qcs = []
        self.ycs = []
        self.agvs = []
        self.yard_blocks = []

        # Activities
        self.berth_being_idle = None
        self.berth_being_occupied = None

        self.vessel_waiting = None
        self.vessel_berthing = None

        self.qc_line_discharging = None
        self.qc_line_loading = None

        self.container_being_discharged = None
        self.container_transporting_to_yard = None
        self.container_being_stacked = None
        self.container_dwelling = None
        self.container_being_unstacked = None
        self.container_transporting_to_quay_side = None
        self.container_being_loaded = None

        self.qc_being_idle = None
        self.qc_setting_up = None
        self.qc_restoring_to_discharge = None
        self.qc_discharging = None
        self.qc_holding_on_discharging = None
        self.qc_restoring_to_load = None
        self.qc_loading = None
        self.qc_holding_on_loading = None

        self.agv_being_idle = None
        self.agv_picking = None
        self.agv_delivering_to_yard = None
        self.agv_holding_at_yard = None
        self.agv_delivering_to_quay_side = None
        self.agv_holding_at_quay_side = None

        self.yc_repositioning = None
        self.yc_picking = None
        self.yc_stacking = None
        self.yc_unstacking = None
        self.yc_holding_on_unstacking = None

        # Conditions
        self._qc_terminate_discharging = False
        self._qc_to_loading = False
        self._qc_terminate_loading = False
        self._yc_in_discharging = False

        # Initialize activities
        self.initialize_activities()        
                
    def quay_side_generator(self):
        """Generate quay-side entities including QCs and AGVs."""
        qc_control_points = FileReader.read_control_points_info(self.qc_control_points_url)

        for berth_id in range(self.number_of_berths):
            qcs = []
            for qc_index in range(self.number_of_qcs_per_berth):
                control_point_id = berth_id * self.number_of_qcs_per_berth + qc_index
                control_point = ControlPoint(
                    id=f"QC_CP{control_point_id}",
                    x_coordinate=qc_control_points[str(control_point_id)][0],
                    y_coordinate=qc_control_points[str(control_point_id)][1]
                )
                
                for agv_index in range(self.number_of_initial_agvs_per_qc):
                    agv_id = berth_id * self.number_of_qcs_per_berth * self.number_of_initial_agvs_per_qc + qc_index * self.number_of_initial_agvs_per_qc + agv_index
                    agv = AGV(id=f"AGV{agv_id}", current_location=control_point)
                    self.agvs.append(agv)
                    self.agv_being_idle.request_to_start(agv)

                qc = QC(id=f"QC{control_point_id}", cp=control_point)
                self.qcs.append(qc)
                qcs.append(qc)
                self.qc_being_idle.request_to_start(qc)

            berth = Berth(id=f"Berth{berth_id}", equipped_qcs=qcs)
            for qc in berth.equipped_qcs:
                qc.located_berth = berth
            self.berths.append(berth)
            self.berth_being_idle.request_to_start(berth)

    def vessel_generator(self):
        """Generate vessels based on the provided container info and arrival times."""
        containers_info = FileReader.read_containers_info(self.containers_info_file_url)
        vessel_arrival_times = FileReader.read_vessel_arrival_times(self.vessel_arrival_times_url)
        number_of_vessels = len(containers_info)

        for orig in range(number_of_vessels):
            discharging_info = containers_info[f"vessel {orig}"]
            loading_info = {
                f"vessel {dest}": containers_info[f"vessel {dest}"].get(f"vessel {orig}", 0)
                for dest in range(number_of_vessels)
            }

            for _week in range(self.running_weeks):
                vessel = Vessel(
                    id=f"vessel {orig}",
                    discharging_containers_information=dict(discharging_info),
                    loading_containers_information=None if _week < self.warm_up_weeks else dict(loading_info),
                    week=_week
                )
                self.vessels.append(vessel)                
                # Generate arrival time with random normal variation
                arrival_time = vessel_arrival_times[f"vessel {orig}"] + timedelta(days=7 * _week)
                normal_time_difference = timedelta(days=2 * self.random.random() - 1)
                
                # Schedule the action correctly
                self.schedule(self.vessel_waiting.request_to_start, 
                     load=vessel, 
                     clock_time=arrival_time + normal_time_difference)
                #print(f"{vessel.id}, {vessel.week}, {arrival_time + normal_time_difference}")

    def yard_generator(self):
        """Generate yard blocks and their corresponding YCs."""
        yc_control_points = FileReader.read_control_points_info("conf//YC_controlpoint.csv")
        self.number_of_ycs = len(yc_control_points)

        for yc_index in range(self.number_of_ycs):
            # Generate control point for each YC
            control_point = ControlPoint(
                id=f"YC_CP{yc_index}",
                x_coordinate=yc_control_points[str(yc_index)][0],
                y_coordinate=yc_control_points[str(yc_index)][1]
            )

            # Generate yard block
            yard_block = YardBlock(
                id=f"Block{yc_index}",
                capacity=self.block_capacity,
                cp=control_point
            )
            self.yard_blocks.append(yard_block)

            # Generate YC
            yc = YC(
                id=f"YC{yc_index}",
                served_block=yard_block,
                cp=control_point
            )
            yard_block.equipped_yc = yc
            self.yc_repositioning.request_to_start(yc)
            self.ycs.append(yc)

    def initialize(self, seed):
        """Initialize the simulation model."""
        self.random = random.Random(seed)  # Set the random seed
        self.quay_side_generator()
        self.vessel_generator()
        self.yard_generator()
        self.warmup(till=self.start_time)

    def initialize_activities(self):
        """Initialize all activities and flow conditions."""
        # Berth activities
        self.berth_being_idle = self.add_child(Berth.BeingIdle())
        self.berth_being_occupied = self.add_child(Berth.BeingOccupied())
        self.berth_being_idle.flow_to(self.berth_being_occupied).flow_to(self.berth_being_idle)

        # Vessel activities
        self.vessel_waiting = self.add_child(Vessel.Waiting())
        self.vessel_berthing = self.add_child(Vessel.Berthing())
        self.vessel_waiting.flow_to(self.vessel_berthing).terminate()

        # QCLine activities
        self.qc_line_discharging = self.add_child(QCLine.Discharging())
        self.qc_line_loading = self.add_child(QCLine.Loading())
        self.qc_line_discharging.flow_to(self.qc_line_loading).terminate()

        # Container activities
        self.container_being_discharged = self.add_child(Container.BeingDischarged())
        self.container_transporting_to_yard = self.add_child(Container.TransportingToYard())
        self.container_being_stacked = self.add_child(Container.BeingStacked())
        self.container_dwelling = self.add_child(Container.Dwelling())
        self.container_being_unstacked = self.add_child(Container.BeingUnstacked())
        self.container_transporting_to_quay_side = self.add_child(Container.TransportingToQuaySide())
        self.container_being_loaded = self.add_child(Container.BeingLoaded())
        self.container_being_discharged.flow_to(self.container_transporting_to_yard) \
            .flow_to(self.container_being_stacked).flow_to(self.container_dwelling) \
            .flow_to(self.container_being_unstacked).flow_to(self.container_transporting_to_quay_side) \
            .flow_to(self.container_being_loaded).terminate()
            
        # QC activities
        self.qc_being_idle = self.add_child(QC.BeingIdle())
        self.qc_setting_up = self.add_child(QC.SettingUp())
        self.qc_restoring_to_discharge = self.add_child(QC.RestoringToDischarge())
        self.qc_discharging = self.add_child(QC.Discharging())
        self.qc_holding_on_discharging = self.add_child(QC.HoldingOnDischarging())
        self.qc_restoring_to_load = self.add_child(QC.RestoringToLoad())
        self.qc_loading = self.add_child(QC.Loading())
        self.qc_holding_on_loading = self.add_child(QC.HoldingOnLoading())

        self.qc_being_idle.flow_to(self.qc_setting_up)\
            .flow_to(self.qc_restoring_to_discharge)\
            .flow_to(self.qc_discharging)\
            .flow_to(self.qc_holding_on_discharging)

        self.qc_holding_on_discharging.flow_to_branch(self.qc_restoring_to_discharge, lambda qc: not self.qc_terminate_discharging(qc, self.qc_restoring_to_discharge))
        self.qc_holding_on_discharging.flow_to_branch(self.qc_restoring_to_load, lambda qc: self._qc_terminate_discharging and self.qc_to_loading(qc, self.qc_restoring_to_load))
        self.qc_holding_on_discharging.flow_to_branch(self.qc_being_idle, lambda qc: self._qc_terminate_discharging and not self._qc_to_loading)

        self.qc_restoring_to_load.flow_to(self.qc_loading)\
            .flow_to(self.qc_holding_on_loading)

        self.qc_holding_on_loading.flow_to_branch(self.qc_restoring_to_load, lambda qc: not self.qc_terminate_loading(qc, self.qc_restoring_to_load))
        self.qc_holding_on_loading.flow_to_branch(self.qc_being_idle, lambda qc: self._qc_terminate_loading)

        # AGV activities
        self.agv_being_idle = self.add_child(AGV.BeingIdle())
        self.agv_picking = self.add_child(AGV.Picking())
        self.agv_delivering_to_yard = self.add_child(AGV.DeliveringToYard())
        self.agv_holding_at_yard = self.add_child(AGV.HoldingAtYard())
        self.agv_delivering_to_quay_side = self.add_child(AGV.DeliveringToQuaySide())
        self.agv_holding_at_quay_side = self.add_child(AGV.HoldingAtQuaySide())

        self.agv_being_idle.flow_to(self.agv_picking)\
            .flow_to_branch(self.agv_delivering_to_yard, lambda agv: agv.in_discharging)

        self.agv_delivering_to_yard.flow_to(self.agv_holding_at_yard)\
            .flow_to(self.agv_being_idle)

        self.agv_picking.flow_to_branch(self.agv_delivering_to_quay_side, lambda agv: not agv.in_discharging)\
            .flow_to(self.agv_holding_at_quay_side)\
            .flow_to(self.agv_being_idle)

        # YC activities
        self.yc_repositioning = self.add_child(YC.Repositioning())
        self.yc_picking = self.add_child(YC.Picking())
        self.yc_stacking = self.add_child(YC.Stacking())
        self.yc_unstacking = self.add_child(YC.Unstacking())
        self.yc_holding_on_unstacking = self.add_child(YC.HoldingOnUnstacking())

        self.yc_repositioning.flow_to(self.yc_picking)\
            .flow_to_branch(self.yc_stacking, lambda yc: self.yc_in_discharging(yc))\
            .flow_to(self.yc_repositioning)

        self.yc_picking.flow_to_branch(self.yc_unstacking, lambda yc: not self._yc_in_discharging)\
            .flow_to(self.yc_holding_on_unstacking)\
            .flow_to(self.yc_repositioning)

        # Berth message conditions
        self.berth_being_idle.on_ready_to_depart += self.qc_being_idle.try_finish
        self.berth_being_occupied.on_start += self.vessel_berthing.try_start
        
        # Vessel message conditions
        self.vessel_waiting.on_ready_to_depart += self.berth_being_idle.try_finish
        self.vessel_berthing.on_start += self.qc_line_discharging.create_qc_line
        self.vessel_berthing.on_ready_to_depart += self.berth_being_occupied.try_finish
        
        # QCLine message conditions
        self.qc_line_discharging.on_start += self.container_being_discharged.generate_containers
        self.qc_line_loading.on_start += self.container_dwelling.try_finish
        self.qc_line_loading.on_ready_to_depart += self.vessel_berthing.try_finish
        
        # Container message conditions
        self.container_being_discharged.on_request_to_start += self.qc_restoring_to_discharge.try_finish
        self.container_being_discharged.on_ready_to_depart += self.agv_being_idle.try_finish
        self.container_transporting_to_yard.on_start += self.qc_holding_on_discharging.try_finish
        self.container_transporting_to_yard.on_ready_to_depart += self.yc_repositioning.try_finish
        self.container_being_stacked.on_start += self.agv_holding_at_yard.try_finish
        self.container_dwelling.on_start += self.qc_line_discharging.try_finish
        self.container_dwelling.on_ready_to_depart += self.agv_being_idle.try_finish
        self.container_transporting_to_quay_side.on_start += self.yc_holding_on_unstacking.try_finish
        self.container_transporting_to_quay_side.on_ready_to_depart += self.qc_restoring_to_load.try_finish
        self.container_being_loaded.on_start += self.agv_holding_at_quay_side.try_finish
        self.container_being_loaded.on_ready_to_depart += self.qc_line_loading.try_finish
        self.container_being_loaded.on_ready_to_depart += self.qc_holding_on_loading.try_finish
        
        # QC message conditions
        self.qc_being_idle.on_start += self.qc_being_idle.re_being_idle_qc
        self.qc_setting_up.on_start += self.vessel_berthing.try_start
        self.qc_discharging.on_start += self.container_being_discharged.try_start
        self.qc_discharging.on_ready_to_depart += self.container_being_discharged.try_finish
        self.qc_loading.on_start += self.container_being_loaded.try_start
        self.qc_loading.on_ready_to_depart += self.container_being_loaded.try_finish
        
        # AGV message conditions
        self.agv_picking.on_start += self.yc_repositioning.try_finish
        self.agv_delivering_to_yard.on_start += self.container_transporting_to_yard.try_start
        self.agv_delivering_to_yard.on_ready_to_depart += self.container_transporting_to_yard.try_finish
        self.agv_delivering_to_quay_side.on_start += self.container_transporting_to_quay_side.try_start
        self.agv_delivering_to_quay_side.on_ready_to_depart += self.container_transporting_to_quay_side.try_finish
        
        # YC message conditions
        self.yc_repositioning.on_start += self.yc_repositioning.re_being_idle_yc
        self.yc_stacking.on_start += self.container_being_stacked.try_start
        self.yc_stacking.on_ready_to_depart += self.container_being_stacked.try_finish
        self.yc_unstacking.on_start += self.container_being_unstacked.try_start
        self.yc_unstacking.on_ready_to_depart += self.container_being_unstacked.try_finish
        self.yc_unstacking.on_ready_to_depart += self.agv_delivering_to_quay_side.try_start


    
    def qc_terminate_discharging(self, qc, restoring_to_discharge):
        """
        Check if QC can terminate discharging.
        """
        _qc_terminate_discharging = False
        num_of_rest_containers = 0

        if qc.served_vessel is not None:
            # Count remaining discharging containers
            for info in qc.served_vessel.discharging_containers_information.values():
                if info != 0:
                    num_of_rest_containers += info
            # Check if we have enough QCs in discharging
            if (
                len([
                    q for q in restoring_to_discharge.processing_list
                    if q.served_vessel.id == qc.served_vessel.id
                ])
                + len([
                    q for q in restoring_to_discharge.pending_list
                    if q.served_vessel.id == qc.served_vessel.id
                ]) == num_of_rest_containers
            ):
                _qc_terminate_discharging = True

        self._qc_terminate_discharging = _qc_terminate_discharging
        return _qc_terminate_discharging

    def qc_to_loading(self, qc, restoring_to_load):
        """
        Check if QC should transition to loading.
        """
        qc_to_loading = False
        num_of_rest_containers = 0

        if qc.served_vessel.loading_containers_information is not None:
            qc_to_loading = True

            # Count remaining loading containers
            for info in qc.served_vessel.loading_containers_information.values():
                if info != 0:
                    num_of_rest_containers += info
            # Check loading conditions
            if (
                len([
                    container for container in restoring_to_load.container_pending_list
                    if container.loading_vessel_id == qc.served_vessel.id
                    and container.week < qc.served_vessel.week
                ]) > 0
                and num_of_rest_containers ==
                len(restoring_to_load.pending_list) +
                len([
                    q for q in restoring_to_load.processing_list
                    if q.served_vessel.id == qc.served_vessel.id
                ]) +
                len([
                    q for q in restoring_to_load.completed_list
                    if q.served_vessel.id == qc.served_vessel.id
                ])
            ):
                qc_to_loading = False

        self._qc_to_loading = qc_to_loading
        return qc_to_loading

    def qc_terminate_loading(self, qc, restoring_to_load):
        """
        Check if QC can terminate loading.
        """
        _qc_terminate_loading = False
        num_of_rest_containers = 0

        if qc.served_vessel is not None:
            # Count remaining loading containers
            for info in qc.served_vessel.loading_containers_information.values():
                if info != 0:
                    num_of_rest_containers += info
            # Check if loading is complete
            if (
                len([
                    q for q in restoring_to_load.pending_list
                    if q.served_vessel == qc.served_vessel
                ])
                + len([
                    q for q in restoring_to_load.processing_list
                    if q.served_vessel == qc.served_vessel
                ])
                + len([
                    q for q in restoring_to_load.completed_list
                    if q.served_vessel == qc.served_vessel
                ]) == num_of_rest_containers
            ):
                _qc_terminate_loading = True

        self._qc_terminate_loading = _qc_terminate_loading
        return _qc_terminate_loading

    def yc_in_discharging(self, yc):
        """
        Check if YC is currently in discharging.
        """
        self._yc_in_discharging = yc.held_container.in_discharging
        return self._yc_in_discharging
