import pandas as pd
import os
import datetime
import random
import string
import argparse
import plotly.graph_objects as go
import plotly.io as pio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CSVProcessor:
    def __init__(self, keyword=None, A=None, a=None, csv_path=None, output_folder=None, B=None, date_col=None):
        self.keyword = keyword
        self.A = A
        self.a = a
        self.csv_path = csv_path
        self.output_folder = output_folder
        self.B = B
        self.date_col = date_col
        self.all_users = None  # To store all possible users for the selected site
        
        if all(arg is None for arg in [keyword, A, a, csv_path, output_folder, B, date_col]):
            self.self_test()
        else:
            self.process_csv()

    def self_test(self):
        # Create a dedicated folder
        test_folder = 'csv_processor_test'
        os.makedirs(test_folder, exist_ok=True)
        
        # Define sample column titles and values
        self.keyword = 'Timestamp'
        self.A = 'Site'
        sites = [f'site{i}' for i in range(1, 11)]
        self.a = random.choice(sites)  # Randomly pick one site as filter value
        self.B = 'User'
        self.date_col = 'Timestamp'
        
        # Define users per site: each site has 10-20 users
        users_per_site = {site: [f'user_{site}_{j}' for j in range(1, random.randint(10, 21))] for site in sites}
        self.all_users = users_per_site[self.a]  # Store all users for the selected site
        
        # Assign users to groups for variance in license occupation
        num_users = len(self.all_users)
        num_high = max(1, num_users // 5)  # 20% high-occupancy users
        num_mid = max(1, num_users // 3)  # 30% mid-occupancy users
        num_low = num_users - num_high - num_mid  # 50% low-occupancy users
        random.shuffle(self.all_users)
        user_groups = {
            'high': self.all_users[:num_high],
            'mid': self.all_users[num_high:num_high + num_mid],
            'low': self.all_users[num_high + num_mid:]
        }
        
        # Create sample CSV data
        header = ['ID', 'Timestamp', 'Site', 'User', 'LicensesOccupied', 'Sub_Period', 'Overdue_History', 'ExtraCol1', 'ExtraCol2']
        
        # Generate random data
        data = []
        # Add some junk rows before header
        data.append(['junk1', 'junk2', 'junk3', 'junk4', 'junk5', 'junk6', 'junk7', 'junk8', 'junk9'])
        data.append(['morejunk', 'another', 'test', 'row', 'before', 'header', 'extra', 'junk', 'data'])
        
        # Add header row which contains the keyword 'Timestamp'
        data.append(header)
        
        # Generate data rows: 10-minute intervals over 3 days
        start_date = datetime.datetime(2025, 8, 1, 0, 0, 0)
        num_days = 3
        intervals_per_day = 24 * 6  # 144 intervals per day
        total_intervals = num_days * intervals_per_day
        
        overdue_options = ['Yes', 'No']
        
        current_time = start_date
        for day in range(num_days):
            # Day-specific min_active for variance in total occupation
            if day == 0:  # Day 1: high occupation (70-100)
                min_active = 70
            elif day == 1:  # Day 2: medium occupation (40-70)
                min_active = 40
            else:  # Day 3: low occupation (20-50)
                min_active = 20
            
            for _ in range(intervals_per_day):
                timestamp_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                for site in sites:
                    users = users_per_site[site]
                    if users:  # Ensure there are users
                        # Select active users with group-based probabilities
                        active_users = []
                        for user in users:
                            if user in user_groups['high'] and random.random() < 0.8:  # 80% active
                                active_users.append(user)
                            elif user in user_groups['mid'] and random.random() < 0.5:  # 50% active
                                active_users.append(user)
                            elif user in user_groups['low'] and random.random() < 0.2:  # 20% active
                                active_users.append(user)
                        
                        # Cap active users to ensure total licenses <= 100
                        random.shuffle(active_users)
                        total_licenses = 0
                        selected_users = []
                        for user in active_users:
                            # Assign licenses based on group
                            if user in user_groups['high']:
                                licenses_occupied = random.randint(10, 14)
                            elif user in user_groups['mid']:
                                licenses_occupied = random.randint(5, 9)
                            else:  # low
                                licenses_occupied = random.randint(1, 4)
                            
                            if total_licenses + licenses_occupied > 100:
                                licenses_occupied = max(0, 100 - total_licenses)
                            if licenses_occupied <= 0:
                                continue
                            total_licenses += licenses_occupied
                            selected_users.append((user, licenses_occupied))
                        
                        # Write data for selected users
                        for user, licenses_occupied in selected_users:
                            id_val = random.randint(1000, 9999)
                            sub_period = random.randint(1, 12)
                            overdue = random.choice(overdue_options)
                            extra1 = random.random()
                            extra2 = ''.join(random.choices(string.ascii_letters, k=5))
                            data.append([id_val, timestamp_str, site, user, licenses_occupied, sub_period, overdue, extra1, extra2])
                current_time += datetime.timedelta(minutes=10)
        
        # Write to CSV
        self.csv_path = os.path.join(test_folder, 'test_data.csv')
        with open(self.csv_path, 'w') as f:
            for row in data:
                f.write(','.join(map(str, row)) + '\n')
        
        # Set output folder
        self.output_folder = test_folder
        
        # Create README.md
        readme_path = os.path.join(test_folder, 'README.md')
        with open(readme_path, 'w') as f:
            f.write('# CSV Processor Self-Test\n\n')
            f.write('Assumed inputs:\n')
            f.write(f'- Keyword: {self.keyword}\n')
            f.write(f'- A (filter column): {self.A}\n')
            f.write(f'- a (filter value): {self.a}\n')
            f.write(f'- CSV path: {self.csv_path}\n')
            f.write(f'- Output folder: {self.output_folder}\n')
            f.write(f'- B (user column): {self.B}\n')
            f.write(f'- Date column: {self.date_col}\n\n')
            f.write('The CSV includes junk rows before the header, and extra columns (ExtraCol1, ExtraCol2) that are not used.\n')
            f.write('Data is generated for 3 days (2025-08-01 to 2025-08-03) with 10-minute intervals.\n')
            f.write('10 sites, each with 10-20 users. Users split into high (20%, 10-14 licenses, 80% active), mid (30%, 5-9 licenses, 50% active), low (50%, 1-4 licenses, 20% active), total capped at 100 licenses per timestamp.\n')
            f.write('Day-specific variance: Day1 high (70-100%), Day2 medium (40-70%), Day3 low (20-50%).\n')
            f.write(f'All users for selected site ({self.a}): {", ".join(self.all_users)}\n')
            f.write('Other columns: LicensesOccupied (1-14), Sub_Period (1-12), Overdue_History (Yes/No).\n')
            f.write('Outputs: occupied_rates.csv (with daily percentages), occupied_rates_graph.html (stacked bar chart of daily user license occupied rates).\n')
        
        # Now process the CSV
        self.process_csv()

    def process_csv(self):
        # Read the entire CSV as list of lists to find header row
        try:
            with open(self.csv_path, 'r') as f:
                lines = [line.strip().split(',') for line in f if line.strip()]
        except FileNotFoundError:
            logging.error(f"CSV file {self.csv_path} not found.")
            raise
        
        # Find the row that contains the keyword
        header_row = None
        header_index = None
        for idx, row in enumerate(lines):
            if any(self.keyword in cell for cell in row):
                header_row = row
                header_index = idx
                break
        
        if header_row is None:
            logging.error(f'Header row containing keyword "{self.keyword}" not found.')
            raise ValueError(f'Header row containing keyword "{self.keyword}" not found.')
        
        # Data rows are after the header
        data_rows = lines[header_index + 1:]
        
        # Create DataFrame with explicit string type for safety
        df = pd.DataFrame(data_rows, columns=header_row, dtype=str)
        
        # Filter rows where A column == a
        if self.A not in df.columns:
            logging.error(f'Column "{self.A}" not found in CSV.')
            raise ValueError(f'Column "{self.A}" not found.')
        df_filtered = df[df[self.A] == str(self.a)].copy()  # Create a copy to avoid SettingWithCopyWarning
        
        # Parse date column
        if self.date_col not in df.columns:
            logging.error(f'Date column "{self.date_col}" not found in CSV.')
            raise ValueError(f'Date column "{self.date_col}" not found.')
        
        if not df_filtered.empty:
            # Log unique values in Timestamp column for debugging
            logging.info(f"Unique values in {self.date_col} before parsing: {df_filtered[self.date_col].unique().tolist()[:10]}")
            
            # Ensure the column is string type before parsing
            df_filtered[self.date_col] = df_filtered[self.date_col].astype(str)
            
            # Convert to datetime, coerce errors to NaT
            df_filtered['timestamp_parsed'] = pd.to_datetime(
                df_filtered[self.date_col], format='%Y-%m-%d %H:%M:%S', errors='coerce'
            )
            
            # Log and filter out rows with invalid datetime values
            invalid_dates = df_filtered[df_filtered['timestamp_parsed'].isna()]
            if not invalid_dates.empty:
                logging.warning(f"Found {len(invalid_dates)} rows with invalid datetime values in {self.date_col}: {invalid_dates[self.date_col].tolist()[:10]}")
                df_filtered = df_filtered[df_filtered['timestamp_parsed'].notna()]
            
            if not df_filtered.empty:
                # Verify datetime type
                logging.info(f"Data type of timestamp_parsed after conversion: {df_filtered['timestamp_parsed'].dtype}")
                if not pd.api.types.is_datetime64_any_dtype(df_filtered['timestamp_parsed']):
                    logging.error(f"Column timestamp_parsed is not datetime type after conversion: {df_filtered['timestamp_parsed'].dtype}")
                    raise ValueError(f"Column timestamp_parsed is not datetime type after conversion.")
                
                # Extract date
                df_filtered['date'] = df_filtered['timestamp_parsed'].dt.date
            else:
                logging.warning(f"All rows for {self.A} = {self.a} have invalid datetime values. No occupied rates will be calculated.")
                results = {}
                sorted_dates = []
                self.all_users = sorted(self.all_users) if self.all_users else []
                self.generate_html_graph(results, sorted_dates)
                return
        else:
            logging.warning(f"No data found for {self.A} = {self.a}. No occupied rates will be calculated.")
            results = {}
            sorted_dates = []
            self.all_users = sorted(self.all_users) if self.all_users else []
            self.generate_html_graph(results, sorted_dates)
            return
        
        # If all_users is not set (i.e., not self-test), get all unique users for the filtered site
        if self.all_users is None:
            self.all_users = sorted(df_filtered[self.B].unique().tolist())
        else:
            self.all_users = sorted(self.all_users)
        
        # For each day, calculate occupied rate of each unique value in B
        if self.B not in df.columns:
            logging.error(f'Column "{self.B}" not found in CSV.')
            raise ValueError(f'Column "{self.B}" not found.')
        
        results = {}
        for date, group in df_filtered.groupby('date'):
            num_intervals = group['timestamp_parsed'].nunique()  # Number of unique timestamps
            if num_intervals > 0:
                # Convert LicensesOccupied to float for precision
                group['LicensesOccupied'] = group['LicensesOccupied'].astype(float)
                
                # Calculate user occupied rates: (sum of licenses / intervals) * 100 / 100
                value_counts = group.groupby(self.B)['LicensesOccupied'].sum()
                occupied_rates = {user: round((value_counts.get(user, 0) / num_intervals) * 100 / 100, 1) for user in self.all_users}
                
                # Calculate site occupied rate: (mean of total licenses per interval) / 100 * 100
                group_by_timestamp = group.groupby('timestamp_parsed')['LicensesOccupied'].sum()
                site_occupied_rate = round((group_by_timestamp.mean() / 100) * 100, 1)
                occupied_rates['Site Total'] = site_occupied_rate
                
                results[date] = occupied_rates
        
        # Sort dates
        sorted_dates = sorted(results.keys())
        
        # Save results to output folder as CSV with percentages
        os.makedirs(self.output_folder, exist_ok=True)
        output_path = os.path.join(self.output_folder, 'occupied_rates.csv')
        with open(output_path, 'w') as f:
            f.write('Date,Value,OccupiedRate\n')
            for date in sorted_dates:
                rates = results[date]
                for value in self.all_users + ['Site Total']:
                    rate = rates[value]
                    f.write(f'{date},{value},{rate}\n')
        
        # Generate HTML graph with Plotly
        self.generate_html_graph(results, sorted_dates)

    def generate_html_graph(self, results, sorted_dates):
        # Create a Plotly figure
        fig = go.Figure()
        
        # Define a list of colors for bars
        colors = [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#E7E9ED',
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#E7E9ED',
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'
        ]  # Enough for 20 users
        
        # Add a bar for each user
        for i, user in enumerate(self.all_users):
            user_data = [results[date].get(user, 0) for date in sorted_dates]
            fig.add_trace(go.Bar(
                x=[str(date) for date in sorted_dates],
                y=user_data,
                name=user,
                marker_color=colors[i % len(colors)]
            ))
        
        # Update layout for stacked bar chart
        fig.update_layout(
            title=f'Daily License Occupied Rates (%) for Site: {self.a if self.a else "Unknown"}',
            xaxis_title='Date (Daily)',
            yaxis_title='Occupied Rate (%)',
            yaxis=dict(range=[0, 100]),
            barmode='stack',
            hovermode='x unified',
            template='plotly_white',
            showlegend=True,
            xaxis=dict(
                tickmode='array',
                tickvals=[str(date) for date in sorted_dates],
                ticktext=[str(date) for date in sorted_dates]
            )
        )
        
        # Save HTML
        html_path = os.path.join(self.output_folder, 'occupied_rates_graph.html')
        pio.write_html(fig, file=html_path, auto_open=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CSV Processor")
    parser.add_argument('--keyword', type=str, default=None, help='Keyword to identify header row')
    parser.add_argument('--A', type=str, default=None, help='Filter column name')
    parser.add_argument('--a', type=str, default=None, help='Filter value for column A')
    parser.add_argument('--csv_path', type=str, default=None, help='Path to the CSV file')
    parser.add_argument('--output_folder', type=str, default=None, help='Output folder path')
    parser.add_argument('--B', type=str, default=None, help='Column for user identification')
    parser.add_argument('--date_col', type=str, default=None, help='Date column name')
    
    args = parser.parse_args()
    
    processor = CSVProcessor(
        keyword=args.keyword,
        A=args.A,
        a=args.a,
        csv_path=args.csv_path,
        output_folder=args.output_folder,
        B=args.B,
        date_col=args.date_col
    )