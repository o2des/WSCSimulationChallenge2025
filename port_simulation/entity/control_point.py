class ControlPoint:
    """Represents a control point in the port simulation."""
    def __init__(self, id: str, x_coordinate: float, y_coordinate: float):
        self.id = id
        self.x_coordinate = x_coordinate
        self.y_coordinate = y_coordinate

    def __str__(self):
        return f"CP[{self.id}]"