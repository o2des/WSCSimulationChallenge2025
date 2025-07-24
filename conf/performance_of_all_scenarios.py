import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Function to load data dynamically based on file path
def load_data(file_path):
    return pd.read_csv(file_path)

# Function to get global min and max values across datasets
def get_global_min_max(data):
    global_min = data.min().min()
    global_max = data.max().max()
    return global_min, global_max

# Specify the file path to read
file_path = "rl_avg_service_time_12agvs.csv"  # Modify to the file path you want to plot

# Load data
data = load_data(file_path).iloc[:, 1:]  # Ignore the first column (seed numbers)

# Prepare data for plotting
data.index = [f"seed {i+1}" for i in range(data.shape[0])]  # Rename rows as seeds
data.columns = [f"scenario {i+1}" for i in range(data.shape[1])]  # Rename columns as scenarios

# Get color range
vmin, vmax = get_global_min_max(data)

# Create heatmap
plt.figure(figsize=(10, 5), dpi=800)  # Set high resolution
plt.imshow(data, cmap="YlGnBu", aspect='auto', vmin=vmin, vmax=vmax)  # Fix color range

# Add color bar
plt.colorbar(label='Value')

# Add axis labels
plt.xlabel("Scenarios", fontsize=10, fontfamily='serif')
plt.ylabel("Seeds", fontsize=10, fontfamily='serif')

# Set axis ticks
plt.xticks(np.arange(len(data.columns)), data.columns, rotation=45, ha='right', fontsize=8, fontfamily='serif')
plt.yticks(np.arange(len(data.index)), data.index, fontsize=8, fontfamily='serif')

# Add values in each cell
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        plt.text(j, i, f"{data.iloc[i, j]:.1f}", ha='center', va='center', color='black', fontsize=7, fontfamily='serif')

# Save heatmap
output_file_name = os.path.join(os.getcwd(), f"{os.path.basename(file_path).split('.')[0]}_heatmap.png")
plt.tight_layout()
plt.savefig(output_file_name, dpi=800)
plt.show()

print(f"Heatmap saved as: {output_file_name}")


