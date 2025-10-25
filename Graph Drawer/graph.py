import matplotlib.pyplot as plt

# Given data
t_squared = [0.369, 0.580, 0.785, 1.047]  # s^2
x_meters = [0.40, 0.60, 0.80, 1.00]       # meters

# Create the plot
plt.figure(figsize=(8, 6))
plt.plot(t_squared, x_meters, 'o', label='Data Points')  # markers only

# Best-fit line (linear regression)
import numpy as np
a, b = np.polyfit(t_squared, x_meters, 1)  # Fit line: x = a*t^2 + b
x_fit = np.linspace(min(t_squared), max(t_squared), 100)
y_fit = a * x_fit + b
plt.plot(x_fit, y_fit, '-', label=f'Best Fit: x = {a:.2f}t² + {b:.2f}')

# Labels and grid
plt.xlabel(r'$t^2$ (s$^2$)')
plt.ylabel('X (m)')
plt.title("Graph of X vs $t^2$")
plt.grid(True)
plt.legend()
plt.tight_layout()

# Show the graph
plt.show()
