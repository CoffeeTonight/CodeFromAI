import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import openpyxl
import json
from openpyxl import load_workbook
import os
import random
from string import ascii_uppercase
from datetime import datetime, timedelta
import argparse

class DataProcessor:
    def __init__(self, csv_file=None, output_dir="OUTPUT_TEST",
                 base_weekly_file="./base_dataset/1_base_weekly_machine_usage_dataset_calc.csv",
                 base_monthly_file="./base_dataset/3_base_monthly_machine_usage_dataset_calc.csv"):
        self.csv_file = csv_file
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.base_weekly_file = base_weekly_file
        self.base_monthly_file = base_monthly_file
        base_dir = os.path.dirname(self.base_weekly_file)
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
        if not os.path.exists(self.base_weekly_file):
            default_df = pd.DataFrame(columns=["Month", "Machine Capacity", "Week", "Sum of Used Machine"])
            default_df.to_csv(self.base_weekly_file, index=False)
            print(f"Created empty base weekly file: {self.base_weekly_file}")
        if not os.path.exists(self.base_monthly_file):
            default_df = pd.DataFrame(columns=["Month", "Machine Capacity", "Week"])
            default_df.to_csv(self.base_monthly_file, index=False)
            print(f"Created empty base monthly file: {self.base_monthly_file}")

        self.output_csv_file = os.path.join(self.output_dir, "3_monthly_machine_usage_dataset.csv")
        self.output_weekly_csv_file = os.path.join(self.output_dir, "2_weekly_machine_usage_dataset_calc.csv")
        self.output_calculated_csv_file = os.path.join(self.output_dir, "2_weekly_machine_usage_dataset_calc.csv")
        self.excel_file = os.path.join(self.output_dir, "report_monthly_machine_usage_dataset_calc.xlsx")
        self.config_file = os.path.join(self.output_dir, "equation_config.json")
        self.html_combined_file = os.path.join(self.output_dir, "report_monthly_machine_usage_trend.html")
        self.html_heatmap_file = os.path.join(self.output_dir, "report_monthly_machine_usage_share_heatmap.html")
        self.df = None
        self.base_cols = None
        self.last_col = None
        self.dTM = {"202001-": 32, "202301-": 64}
        self.config = self._create_minimal_config()
        self.default_cols = ["Month", "Machine Capacity", "Week", "Sum of Used Machine"]

    def _create_minimal_config(self):
        config = {
            "Average Usage": {"type": "equation", "equation": "AVERAGE({base_cols})"},
            "Peak Usage": {"type": "equation", "equation": "MAX({base_cols})"},
            "Average Usage Ratio": {"type": "equation", "equation": "Average Usage / Machine Capacity"},
            "Peak Usage Ratio": {"type": "equation", "equation": "Peak Usage / Machine Capacity"},
            "{col}_Ratio": {"type": "equation", "equation": "{col} / Machine Capacity"},
            "{col}_Share": {"type": "equation", "equation": "{col} / Sum of Used Machine"}
        }
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=4)
        return config

    def generate_random_data(self, weeks=3, base_cols="A:P"):
        self.base_cols = [col for col in ascii_uppercase if col >= base_cols[0] and col <= base_cols[-1]]
        self.last_col = self.base_cols[-1]

        years = list(range(2022, 2026))
        weeks_list = set()
        while len(weeks_list) < weeks:
            year = random.choice(years)
            week_num = random.randint(1, 52)
            week_str = f"{year}-W{week_num:02d}"
            weeks_list.add(week_str)
        weeks_list = sorted(list(weeks_list))

        data = {
            "Week": weeks_list,
            "Machine Capacity": [],
        }
        for col in self.base_cols:
            data[col] = [0.0] * len(weeks_list)

        for i, week in enumerate(weeks_list):
            month = pd.to_datetime(f"{week.split('-')[0]}-W{week.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w").strftime("%Y%m")
            tm = self.dTM["202001-"] if month < "202301" else self.dTM["202301-"]
            data["Machine Capacity"].append(tm)

            active_cols = self.base_cols[:6] if tm == 32 else self.base_cols
            value_list = [random.uniform(3, 12) for _ in range(len(active_cols))]
            initial_sum = sum(value_list)
            scale_factor = (tm - len(active_cols) * 3) / (initial_sum - len(active_cols) * 3)
            scaled_values = []
            for val in value_list:
                scaled_val = 3 + (val - 3) * scale_factor
                scaled_values.append(max(3, min(12, round(scaled_val, 1))))
            total = sum(scaled_values)
            if total > tm:
                diff = total - tm
                min_idx = scaled_values.index(min(scaled_values))
                scaled_values[min_idx] = max(3, round(scaled_values[min_idx] - diff, 1))

            random.shuffle(scaled_values)
            for idx, col in enumerate(active_cols):
                data[col][i] = scaled_values[idx]

        df = pd.DataFrame(data)
        df["Week"] = df["Week"].apply(lambda x: pd.to_datetime(f"{x.split('-')[0]}-W{x.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w"))
        df["Month"] = df["Week"].dt.to_period("M").astype(str)
        df["Sum of Used Machine"] = df[self.base_cols].sum(axis=1)
        self.df = df[["Month", "Machine Capacity", "Week"] + self.base_cols + ["Sum of Used Machine"]]
        self.df = self.df.fillna(0)
        self.df = self.df.sort_values(by="Week", ascending=False)
        self.df.to_csv(self.output_weekly_csv_file, index=False)

    def generate_all_weeks_data(self, start_date="2022-01-01", end_date="2025-03-31", base_cols="A:P"):
        self.base_cols = [col for col in ascii_uppercase if col >= base_cols[0] and col <= base_cols[-1]]
        self.last_col = self.base_cols[-1]

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        weeks_list = []
        current = start
        while current <= end:
            week_str = current.strftime("%Y-W%W")
            weeks_list.append(week_str)
            current += timedelta(days=7)
        weeks_list = sorted(list(set(weeks_list)))

        data = {
            "Week": weeks_list,
            "Machine Capacity": [],
        }
        for col in self.base_cols:
            data[col] = [0.0] * len(weeks_list)

        for i, week in enumerate(weeks_list):
            month = pd.to_datetime(f"{week.split('-')[0]}-W{week.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w").strftime("%Y%m")
            tm = self.dTM["202001-"] if month < "202301" else self.dTM["202301-"]
            data["Machine Capacity"].append(tm)

            active_cols = self.base_cols[:6] if tm == 32 else self.base_cols
            value_list = [random.uniform(3, 12) for _ in range(len(active_cols))]
            initial_sum = sum(value_list)
            scale_factor = (tm - len(active_cols) * 3) / (initial_sum - len(active_cols) * 3)
            scaled_values = []
            for val in value_list:
                scaled_val = 3 + (val - 3) * scale_factor
                scaled_values.append(max(3, min(12, round(scaled_val, 1))))
            total = sum(scaled_values)
            if total > tm:
                diff = total - tm
                min_idx = scaled_values.index(min(scaled_values))
                scaled_values[min_idx] = max(3, round(scaled_values[min_idx] - diff, 1))

            random.shuffle(scaled_values)
            for idx, col in enumerate(active_cols):
                data[col][i] = scaled_values[idx]

        df = pd.DataFrame(data)
        df["Week"] = df["Week"].apply(lambda x: pd.to_datetime(f"{x.split('-')[0]}-W{x.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w"))
        df["Month"] = df["Week"].dt.to_period("M").astype(str)
        df["Sum of Used Machine"] = df[self.base_cols].sum(axis=1)
        df = df[["Month", "Machine Capacity", "Week"] + self.base_cols + ["Sum of Used Machine"]]
        df = df.fillna(0)
        df = df.sort_values(by="Week", ascending=False)
        self.df = df
        self.df.to_csv(self.output_weekly_csv_file, index=False)

    def load_and_convert_data(self):
        if not self.csv_file or not os.path.exists(self.csv_file):
            print(f"Warning: CSV file '{self.csv_file}' not found or not provided. Data will be generated if running in test mode.")
            return
        df = pd.read_csv(self.csv_file)
        df.columns = [col.lower() for col in df.columns]
        self.base_cols = [col for col in df.columns if "machine capacity" not in col and "week" not in col and "month" not in col and "sum" not in col.lower()]
        self.last_col = self.base_cols[-1]

        df["week"] = pd.to_datetime(df["week"])
        df["month"] = df["week"].dt.to_period("M").astype(str)
        df["sum of used machine"] = df[self.base_cols].sum(axis=1) if "sum of used machine" not in df.columns else df["sum of used machine"]
        self.df = df[["month", "machine capacity", "week"] + self.base_cols + ["sum of used machine"]]
        self.df.columns = ["Month", "Machine Capacity", "Week"] + [col.capitalize() for col in self.base_cols] + ["Sum of Used Machine"]
        self.df = self.df.fillna(0)
        self.df = self.df.sort_values(by="Week", ascending=False)
        self.df.to_csv(self.output_weekly_csv_file, index=False)

    def calculate_columns(self):
        if self.df is None:
            return
        base_cols_cap = [col.capitalize() for col in self.base_cols]
        print(f"Debug: DataFrame columns before calculation: {list(self.df.columns)}")

        for col in ["Average Usage", "Peak Usage", "Average Usage Ratio", "Peak Usage Ratio"]:
            if col in self.config:
                if col == "Average Usage":
                    self.df[col] = self.df[base_cols_cap].mean(axis=1)
                elif col == "Peak Usage":
                    self.df[col] = self.df[base_cols_cap].max(axis=1)
                elif col == "Average Usage Ratio":
                    self.df[col] = self.df["Average Usage"] / self.df["Machine Capacity"]
                elif col == "Peak Usage Ratio":
                    self.df[col] = self.df["Peak Usage"] / self.df["Machine Capacity"]

        for col, config in self.config.items():
            if "{col}" in col:
                for base_col in base_cols_cap:
                    actual_col = col.replace("{col}", base_col)
                    equation = config["equation"].replace("{col}", base_col)
                    if "Machine Capacity" in equation:
                        self.df[actual_col] = self.df[base_col] / self.df["Machine Capacity"]
                    elif "Sum of Used Machine" in equation:
                        self.df[actual_col] = self.df[base_col] / self.df["Sum of Used Machine"]

        self.df = self.df.fillna(0)
        print(f"Debug: DataFrame columns after calculation: {list(self.df.columns)}")
        self.df.to_csv(self.output_calculated_csv_file, index=False)

    def convert_to_monthly(self):
        if self.df is None:
            return None
        agg_dict = {
            "Machine Capacity": "mean",
            "Week": "max",
            "Sum of Used Machine": "mean",
            "Average Usage": "mean",
            "Peak Usage": "mean",
            "Average Usage Ratio": "mean",
            "Peak Usage Ratio": "mean",
        }
        for col in self.base_cols + [f"{col}_Ratio" for col in self.base_cols] + [f"{col}_Share" for col in self.base_cols]:
            if col.capitalize() in self.df.columns:
                agg_dict[col.capitalize()] = "mean"

        monthly_df = self.df.groupby("Month").agg(agg_dict).reset_index()
        monthly_df = monthly_df.sort_values(by="Week", ascending=False)
        monthly_df = monthly_df.fillna(0)
        return monthly_df

    def save_combined_html(self):
        if os.path.exists(self.base_monthly_file):
            df = pd.read_csv(self.base_monthly_file)
            df["Week"] = pd.to_datetime(df["Week"])
            df = df.sort_values(by="Week", ascending=True)
            df_table = df.sort_values(by="Week", ascending=False)
        else:
            print(f"Warning: No base monthly data found at {self.base_monthly_file}")
            return

        base_cols_cap = [col for col in [c.capitalize() for c in self.base_cols] if col in df.columns]
        if not base_cols_cap:
            print(f"Warning: No machine columns found in {self.base_monthly_file}. Using empty list.")
            base_cols_cap = []

        if base_cols_cap:
            sorted_cols = df[base_cols_cap].mean().sort_values(ascending=False).index.tolist()
        else:
            sorted_cols = []

        fig = make_subplots(rows=2, cols=1,
                            subplot_titles=("Machine Usage Trend", "Machine Usage Trend Breakdown"),
                            specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
                            vertical_spacing=0.2)

        # First graph: Sum of Machine Operation (left), Operation Ratio (right, 0-100%)
        fig.add_trace(go.Bar(x=df["Month"], y=df["Sum of Used Machine"], name="Sum of Machine Operation", marker_color="blue"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["Month"], y=df["Average Usage Ratio"] * 100, name="Operation Ratio (%)", mode="lines", line=dict(color="red")), row=1, col=1, secondary_y=True)

        # Second graph: Sorted stacked bars with line graphs for each item
        colors = px.colors.qualitative.Plotly
        for i, col in enumerate(sorted_cols):
            if col in df.columns:
                # Add bar
                fig.add_trace(go.Bar(x=df["Month"], y=df[col], name=f"{col} Usage", marker_color=colors[i % len(colors)]), row=2, col=1)
                # Add line graph for the same item
                fig.add_trace(go.Scatter(x=df["Month"], y=df[col], name=f"{col} Usage Line", mode="lines", line=dict(color=colors[i % len(colors)], dash="dash"), opacity=0.7), row=2, col=1)

        fig.update_layout(
            height=1000,
            width=None,
            autosize=True,
            title_text="Machine Usage Trends (2022-2025)",
            title_font_size=16,
            barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5, font=dict(size=16)),
            showlegend=True,
            margin=dict(l=50, r=50, t=100, b=150),
            font=dict(size=16)
        )

        # First graph axis updates
        fig.update_yaxes(title_text="Sum of Machine Operation", title_font_size=16, tickfont_size=16, row=1, col=1)
        fig.update_yaxes(title_text="Operation Ratio (%)", title_font_size=16, tickfont_size=16, range=[0, 100], row=1, col=1, secondary_y=True)
        fig.update_xaxes(title_text="Month", title_font_size=16, tickfont_size=16, tickangle=45, tickmode="auto", nticks=20, row=1, col=1)

        # Second graph axis updates
        fig.update_yaxes(title_text="Average Machine Usage", title_font_size=16, tickfont_size=16, row=2, col=1)
        fig.update_xaxes(title_text="Month", title_font_size=16, tickfont_size=16, tickangle=45, tickmode="auto", nticks=20, row=2, col=1)

        graph_html = fig.to_html(full_html=False, include_plotlyjs="cdn")
        html_table = df_table.to_html(index=False, classes="table table-striped", border=0)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Machine Usage Trends and Data</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ text-align: center; font-size: 16px; }}
                .table {{ width: 100%; border-collapse: collapse; margin-top: 60px; font-size: 16px; }}
                .table th, .table td {{ padding: 8px; text-align: left; }}
                .table-striped tbody tr:nth-child(odd) {{ background-color: #f2f2f2; }}
                .graph-container {{ margin-top: 40px; width: 90vw; max-width: 100%; margin-left: auto; margin-right: auto; margin-bottom: 60px; }}
            </style>
        </head>
        <body>
            <h1>Machine Usage Trends and Data (2022-2025)</h1>
            <div class="graph-container">
                {graph_html}
            </div>
            <h2>TM-Usage Data Table (Monthly Calculations)</h2>
            {html_table}
        </body>
        </html>
        """

        with open(self.html_combined_file, "w") as f:
            f.write(html_content)

    def save_heatmap_html(self):
        if os.path.exists(self.base_monthly_file):
            df = pd.read_csv(self.base_monthly_file)
            df["Week"] = pd.to_datetime(df["Week"])
            df = df.sort_values(by="Week", ascending=True)
        else:
            print(f"Warning: No base monthly data found at {self.base_monthly_file}")
            return

        base_cols_cap = [col for col in [c.capitalize() for c in self.base_cols] if col in df.columns]
        if not base_cols_cap:
            print(f"Warning: No machine columns (e.g., A, B, C) found in {self.base_monthly_file}. Heatmap cannot be generated.")
            return

        df = df.fillna(0)
        heatmap_data = df[base_cols_cap].div(df["Sum of Used Machine"], axis=0).fillna(0) * 100

        fig = go.Figure(data=go.Heatmap(
            x=df["Month"],
            y=base_cols_cap,
            z=heatmap_data.T,
            colorscale="Viridis",
            name="Usage Share (%)",
            showscale=True
        ))

        fig.update_layout(
            height=600,
            width=None,
            autosize=True,
            title_text="Machine Usage Share Heatmap (2022-2025)",
            title_font_size=16,
            margin=dict(l=50, r=50, t=100, b=100),
            font=dict(size=16)
        )
        fig.update_xaxes(
            title_text="Month",
            title_font_size=16,
            tickfont_size=16,
            tickangle=45,
            tickmode="auto",
            nticks=20
        )
        fig.update_yaxes(
            title_text="Machine",
            title_font_size=16,
            tickfont_size=16
        )

        heatmap_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Machine Usage Share Heatmap</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ text-align: center; font-size: 16px; }}
                .graph-container {{ width: 90vw; max-width: 100%; margin-left: auto; margin-right: auto; margin-bottom: 60px; }}
            </style>
        </head>
        <body>
            <h1>Machine Usage Share Heatmap (2022-2025)</h1>
            <div class="graph-container">
                {heatmap_html}
            </div>
        </body>
        </html>
        """

        with open(self.html_heatmap_file, "w") as f:
            f.write(html_content)

    def update_excel_sheet(self):
        if os.path.exists(self.base_weekly_file):
            base_weekly_df = pd.read_csv(self.base_weekly_file)
            base_weekly_df["Week"] = pd.to_datetime(base_weekly_df["Week"])
            print(f"Debug: Loaded base_weekly_df columns: {list(base_weekly_df.columns)}")
        else:
            base_weekly_df = pd.DataFrame(columns=self.default_cols)
            print(f"Debug: Initialized base_weekly_df columns: {list(base_weekly_df.columns)}")

        if self.df is not None:
            common_cols_weekly = list(set(self.df.columns) & set(base_weekly_df.columns))
            if not common_cols_weekly:
                common_cols_weekly = self.default_cols
                base_weekly_df = pd.DataFrame(columns=common_cols_weekly)
            updated_weekly_df = pd.concat([self.df, base_weekly_df[~base_weekly_df["Week"].isin(self.df["Week"])]], ignore_index=True)
            updated_weekly_df = updated_weekly_df.sort_values(by="Week", ascending=False)
            updated_weekly_df = updated_weekly_df.fillna(0)
            updated_weekly_df.to_csv(self.base_weekly_file, index=False)

            monthly_df = self.convert_to_monthly()
            if monthly_df is not None:
                updated_df = monthly_df
                updated_df = updated_df.sort_values(by="Week", ascending=False)
                updated_df.to_excel(self.excel_file, index=False)
                updated_df.to_csv(self.output_csv_file, index=False)

        wb = load_workbook(self.excel_file)
        ws = wb.active

        vba_code = """
        Private Sub Workbook_Open()
            Dim ws As Worksheet
            Dim chartObj As ChartObject
            Dim rng As Range

            Set ws = ThisWorkbook.Sheets("Sheet1")
            For Each chartObj In ws.ChartObjects
                chartObj.Delete
            Next chartObj

            Set rng = ws.Range("A1:" & ws.Cells(1, ws.Columns.Count).End(xlToLeft).Address)

            With ws.DropDowns.Add(100, 10, 100, 15)
                .ListFillRange = "=A2:A" & ws.Cells(ws.Rows.Count, "A").End(xlUp).Row
                .LinkedCell = "$B$1"
            End With

            ws.Range("A1").AutoFilter Field:=1, Criteria1:=ws.Range("B1").Value
            Set rng = ws.Range("A1:" & ws.Cells(ws.Rows.Count, "A").End(xlUp).Address).SpecialCells(xlCellTypeVisible)

            Set chartObj = ws.ChartObjects.Add(Left:=200, Top:=50, Width:=500, Height:=300)
            With chartObj.Chart
                .SetSourceData Source:=rng
                .ChartType = xlLineMarkers
                .HasTitle = True
                .ChartTitle.Text = "Monthly Trend for " & ws.Range("B1").Value
                .Axes(xlCategory).HasTitle = True
                .Axes(xlCategory).AxisTitle.Text = "Columns"
                .Axes(xlValue).HasTitle = True
                .Axes(xlValue).AxisTitle.Text = "Values"
            End With
        End Sub
        """

        try:
            wb.vba_project.add_module("Module1", vba_code)
            wb.save(self.excel_file)
            print(f"VBA 모듈이 삽입되었습니다: {self.excel_file}")
        except AttributeError:
            with open(os.path.join(self.output_dir, "vba_code.txt"), "w") as f:
                f.write(vba_code)
            wb.save(self.excel_file)
            print(f"경고: VBA 모듈 삽입 실패. 'vba_code.txt'를 {self.output_dir}에 저장했습니다.")

    def update_base_monthly(self):
        if os.path.exists(self.base_weekly_file):
            weekly_df = pd.read_csv(self.base_weekly_file)
            weekly_df["Week"] = pd.to_datetime(weekly_df["Week"])
            weekly_df["Month"] = weekly_df["Week"].dt.to_period("M").astype(str)
        else:
            print(f"Warning: No base weekly data found at {self.base_weekly_file}")
            return

        self.df = weekly_df
        self.calculate_columns()
        monthly_df = self.convert_to_monthly()

        if os.path.exists(self.base_monthly_file):
            existing_monthly_df = pd.read_csv(self.base_monthly_file)
        else:
            existing_monthly_df = pd.DataFrame(columns=["Month", "Machine Capacity", "Week"])

        new_months = set(monthly_df["Month"])
        unchanged_months_df = existing_monthly_df[~existing_monthly_df["Month"].isin(new_months)]
        updated_monthly_df = pd.concat([unchanged_months_df, monthly_df], ignore_index=True)
        updated_monthly_df = updated_monthly_df.sort_values(by="Week", ascending=False)
        updated_monthly_df = updated_monthly_df.fillna(0)
        updated_monthly_df.to_csv(self.base_monthly_file, index=False)
        print(f"Updated base monthly dataset: {self.base_monthly_file}")

    def process(self):
        self.load_and_convert_data()
        if self.df is not None:
            self.calculate_columns()
            self.update_excel_sheet()
            self.update_base_monthly()
            self.save_combined_html()
            self.save_heatmap_html()

def test_basic_set(base_weekly_file):
    print("\nRunning Basic Set Tests (Small Tests)")

    dummy_configs = [
        ("OUTPUT_TEST1", "test1_weekly_data.csv", 20),
        ("OUTPUT_TEST2", "test2_weekly_data.csv", 2),
        ("OUTPUT_TEST3", "test3_weekly_data.csv", 1)
    ]

    for output_dir, filename, weeks in dummy_configs:
        processor = DataProcessor(output_dir=output_dir, base_weekly_file=base_weekly_file)
        processor.generate_random_data(weeks=weeks, base_cols="A:P")
        dummy_file = os.path.join(output_dir, filename)
        processor.df.to_csv(dummy_file, index=False)
        print(f"Created dummy dataset: {dummy_file}")

        processor_with_input = DataProcessor(csv_file=dummy_file, output_dir=output_dir, base_weekly_file=base_weekly_file)
        processor_with_input.process()
        print(f"Processed Test with input: {dummy_file}")

def test_real_set(base_weekly_file):
    print("\nRunning Real Set Test (Big Test)")

    output_dir = "OUTPUT_TEST_BIG"
    dummy_file = os.path.join(output_dir, "big_test_weekly_data.csv")

    processor = DataProcessor(output_dir=output_dir, base_weekly_file=base_weekly_file)
    processor.generate_all_weeks_data(start_date="2022-01-01", end_date="2025-03-31", base_cols="A:G")
    processor.df.to_csv(dummy_file, index=False)
    print(f"Created dummy dataset: {dummy_file}")

    processor_with_input = DataProcessor(csv_file=dummy_file, output_dir=output_dir, base_weekly_file=base_weekly_file)
    processor_with_input.process()
    print(f"Processed Test with input: {dummy_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process machine usage data with optional input CSV file.")
    parser.add_argument("--input", type=str, help="Path to the input CSV file", default=None)
    args = parser.parse_args()

    base_weekly_file = "./base_dataset/1_base_weekly_machine_usage_dataset_calc.csv"
    base_monthly_file = "./base_dataset/3_base_monthly_machine_usage_dataset_calc.csv"

    if args.input:
        print(f"Running with input file: {args.input}")
        processor = DataProcessor(csv_file=args.input, output_dir="OUTPUT_CUSTOM",
                                 base_weekly_file=base_weekly_file, base_monthly_file=base_monthly_file)
        processor.process()
        print(f"\nProcessed input file: {args.input}")
        print(f"All weekly data accumulated in {base_weekly_file}")
        print(f"Base monthly data updated in {base_monthly_file}")
        print(f"Local results saved in OUTPUT_CUSTOM/")
    else:
        print("No input file provided. Running test suite...")
        #test_basic_set(base_weekly_file)
        test_real_set(base_weekly_file)
        print(f"\nAll test data accumulated in {base_weekly_file}")
        print(f"Base monthly data updated in {base_monthly_file}")
        print("Test results saved in OUTPUT_TEST*/ directories")
