import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def create_and_save_matrix(a, b, index):
    # Create a random integer matrix of size (a) x (a)
    matrix = np.random.randint(0, b + 1, size=(a, a))
    # Set the diagonal elements to 0
    np.fill_diagonal(matrix, 0)
    # Convert matrix to DataFrame
    df = pd.DataFrame(matrix)
    # Generate labels for the rows and columns
    labels = [f"vessel {i}" for i in range(a)]
    df.index = labels
    df.columns = labels
    # Save DataFrame to CSV without any decimal places
    df.to_csv('transhipment'+ str(index) +'.csv', float_format='%.0f')

def create_sorted_vessel_arrival_table(a, rate, index):
    vessels = [f"vessel {i}" for i in range(a)]
    # Generate time deltas using exponential distribution (in minutes)
    time_deltas = np.random.exponential(scale=1 / rate, size=a)
    # Calculate cumulative time to simulate vessels arriving in sequence
    cumulative_time_deltas = np.cumsum(time_deltas) % 10080  # Ensure time is within a week
    start_time = datetime.now().replace(month=5, day=4, hour=0, minute=0, second=0, microsecond=0)
    arrival_times = [start_time + timedelta(minutes=int(delta)) for delta in cumulative_time_deltas]
    arrival_times.sort()
    # Format arrival times to show exact time in the specified format
    formatted_times = [time.strftime('%Y/%m/%d %H:%M:%S') for time in arrival_times]
    df = pd.DataFrame({
        'Vessel': vessels,
        'Arrival Time': formatted_times
    })
    # Save DataFrame to CSV without column headers
    df.to_csv('vessel_arrival_time'+ str(index) +'.csv', index=False, header=False)


# Main script
NumberofVessels = 30;
if __name__ == '__main__':
    for i in range(0, NumberofVessels):
        create_and_save_matrix(NumberofVessels, 13, i)
        create_sorted_vessel_arrival_table(NumberofVessels, 1 / 504, i)
