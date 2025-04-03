# TM-Usage Report Generator

This Python script generates and updates a TM (Total Machine)-Usage report in an Excel file with VBA-generated graphs and a Plotly HTML graph, designed to work across Linux and Windows environments.

## Requirements

### 1. Initial Data Generation
- **Description**: Generate a random TM-Usage report as an Excel sheet.
- **Details**: Includes "Week", "Total Machine", and usage columns "A" to "P" for 3 weeks. TM values are either 32 or 64, with A-P values summing up to TM or less.
- **Output**: `stacked_data.xlsx`

### 2. Base Data Usage
- **Description**: Use the generated random data as the base dataset for subsequent real data inputs.
- **Details**: Saved as `stacked_data.xlsx`, updated with CSV inputs.

### 3. CSV Data Processing
- **Description**: Process weekly data from CSV files and verify results.
- **Details**: CSV includes "Week", "Total Machine", and "A" to "P". Weekly data is aggregated to monthly. Usage columns are filtered by excluding "total" and "week" (case-insensitive).
- **Input**: `input_data.csv`

### 4. Automation Integration
- **Description**: Enable integration into other Python scripts for automation.
- **Details**: Implemented as a modular `DataProcessor` class with `__main__` execution support.

### 5. Graph Generation
- **Description**: Create dual graphs: Plotly HTML and VBA-generated Excel graph.
- **Details**:
  - **Plotly**: Outputs "Average Usage Ratio" trend as `trend_graph.html`.
  - **VBA**: Inserts code to generate a dropdown and line graph in Excel when opened in Windows.

### 6. Data Stacking
- **Description**: Update the report weekly by stacking new data at the top of the Excel sheet.
- **Details**: Maintains existing data, removes duplicate months.
- **Output**: `output_interactive.xlsx`

### 7. Usage Data Format
- **Description**: Base stacked data includes only "Week" and usage values (A-P).
- **Details**: "Total Machine" is calculated from CSV or estimated as the sum of A-P.

### 8. Linux VBA Graph Support
- **Description**: Generate an MS Excel file with VBA-generated graphs from Linux.
- **Details**: VBA code inserted for Windows compatibility, executed when opened in MS Excel.

### 9. Windows Compatibility
- **Description**: Ensure the file works in Windows MS Excel from a Linux system.
- **Details**: VBA insertion verified; manual addition option provided if automated insertion fails.

## Installation

- **Python Packages**:
  ```bash
  pip install pandas plotly openpyxl



  "I’d like you to create a Python script for analyzing machine usage trends over time. Here’s what I need:

    Purpose: Generate and visualize machine usage data to track trends monthly and weekly.
    Key Features:
        Generate random weekly data for machines (e.g., columns A to P) from 2022 to 2025 with a 'Machine Capacity' that changes (32 before 2023, 64 after).
        Calculate monthly aggregates including average usage, peak usage, ratios, and shares for each machine.
        Create two graphs:
            First graph: Bar chart of total machine operation with a line for operation ratio (as a percentage, 0-100).
            Second graph: Sorted stacked bar chart (largest at bottom) with lines for each machine’s usage.
        Save a heatmap showing monthly usage shares per machine.
        Support command-line input for a custom CSV file or run tests if no input is provided.
    Input/Output:
        Input: Optional CSV file via --input argument (e.g., weekly data with Week, Machine Capacity, A, B, etc.).
        Output: CSV files for weekly and monthly data in ./base_dataset/, an Excel report with VBA, and HTML files for graphs in an output directory (e.g., OUTPUT_TEST_BIG).
    Constraints/Preferences:
        Use pandas for data handling, plotly for graphs, and openpyxl for Excel.
        Text size in graphs should be 16.
        Sort the stacked bars in the second graph by mean usage, largest at bottom.
    Optional Details:
        Start with a test suite for small datasets (e.g., 20, 2, 1 weeks) and a big test (2022-2025).
        Store cumulative data in ./base_dataset/ for persistence."

Tips for Future Requests

    Be Specific: Detail what you want (e.g., "add a third graph showing peak usage per machine" or "change the heatmap colors to blue shades").
    Reference Existing Code: If modifying this script, say, "Update the existing script to..." and specify changes (e.g., "add a new column X" or "sort by month instead of week").
    Provide Examples: If possible, give a sample input/output or sketch of a graph to clarify your vision.
    Ask Questions: If unsure, ask me for options (e.g., "What’s the best way to add a trend line?").

Example for a Future Modification

"I want you to modify this script to add a new feature:

    Purpose: Include a trend analysis for peak usage.
    Key Features: Add a third subplot to the combined HTML graph showing peak usage per machine as lines, sorted by highest peak.
    Input/Output: Use the existing monthly dataset (3_base_monthly_machine_usage_dataset_calc.csv), output to the same HTML file.
    Constraints: Keep text size at 16, use distinct colors for each machine."

This format keeps our communication clear and efficient. Feel free to adapt it to your needs when asking me to make or tweak scripts in the future! How would you like to proceed next?
