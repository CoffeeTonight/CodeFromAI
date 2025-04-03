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

class DataProcessor:
    def __init__(self, csv_file=None, output_dir="OUTPUT_MUT_TEST_STEP1",
                 base_weekly_file="./base_dataset/1_base_weekly_machine_usage_dataset_calc.csv"):
        self.csv_file = csv_file
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        # Check and create base_weekly_file if it doesn't exist
        self.base_weekly_file = base_weekly_file
        base_dir = os.path.dirname(self.base_weekly_file)
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
        if not os.path.exists(self.base_weekly_file):
            # Create empty file with default columns
            default_df = pd.DataFrame(columns=["Month", "Machine Capacity", "Week"] +
                                     [col for col in ascii_uppercase[:16]] + ["Sum of Used Machine"])
            default_df.to_csv(self.base_weekly_file, index=False)
            print(f"Created empty base file: {self.base_weekly_file}")

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
        self.dTM = {"202001-": 32, "202301-": 64}  # Machine Capacity 값
        self.config = self._create_minimal_config()
        self.default_cols = ["Month", "Machine Capacity", "Week"] + [col for col in ascii_uppercase[:16]] + ["Sum of Used Machine"]

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

        data = {"Week": weeks_list}
        tm_values = []
        for week in weeks_list:
            month = pd.to_datetime(f"{week.split('-')[0]}-W{week.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w").strftime("%Y%m")
            if month < "202301":
                tm_values.append(self.dTM["202001-"])
            else:
                tm_values.append(self.dTM["202301-"])
        data["Machine Capacity"] = tm_values

        for i, tm in enumerate(tm_values):
            active_cols = self.base_cols[:6] if tm == 32 else self.base_cols
            remaining = tm
            values = {}
            total = 0
            for col in active_cols[:-1]:
                val = random.uniform(0, min(remaining, tm - total) / len(active_cols))
                values[col] = round(val, 1)
                total += values[col]
                remaining -= values[col]
            values[active_cols[-1]] = round(min(remaining, tm - total), 1)
            for col in self.base_cols:
                data[col] = data.get(col, [])
                data[col].append(values.get(col, 0.0))

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

        data = {"Week": weeks_list}
        tm_values = []
        for week in weeks_list:
            month = pd.to_datetime(f"{week.split('-')[0]}-W{week.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w").strftime("%Y%m")
            if month < "202301":
                tm_values.append(self.dTM["202001-"])
            else:
                tm_values.append(self.dTM["202301-"])
        data["Machine Capacity"] = tm_values

        for i, tm in enumerate(tm_values):
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
            values = {col: scaled_values[idx] for idx, col in enumerate(active_cols)}

            for col in self.base_cols:
                data[col] = data.get(col, [])
                data[col].append(values.get(col, 0.0))

        df = pd.DataFrame(data)
        df["Week"] = df["Week"].apply(lambda x: pd.to_datetime(f"{x.split('-')[0]}-W{x.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w"))
        df["Month"] = df["Week"].dt.to_period("M").astype(str)
        df["Sum of Used Machine"] = df[self.base_cols].sum(axis=1)
        df = df[["Month", "Machine Capacity", "Week"] + self.base_cols + ["Sum of Used Machine"]]
        df = df.fillna(0)
        df = df.sort_values(by="Week", ascending=False)

        group1_end = pd.to_datetime("2023-01-16")
        group2_end = pd.to_datetime("2024-02-12")

        group1 = df[df["Week"] <= group1_end]
        group2 = df[(df["Week"] > group1_end) & (df["Week"] <= group2_end)]
        group3 = df[df["Week"] > group2_end]

        group1.to_csv(os.path.join(self.output_dir, "group1_weekly_data.csv"), index=False)
        group2.to_csv(os.path.join(self.output_dir, "group2_weekly_data.csv"), index=False)
        group3.to_csv(os.path.join(self.output_dir, "group3_weekly_data.csv"), index=False)

        self.df = df
        self.df.to_csv(self.output_weekly_csv_file, index=False)

    def load_and_convert_data(self):
        if not self.csv_file or not os.path.exists(self.csv_file):
            print(f"Warning: CSV file '{self.csv_file}' not found. Skipping CSV data loading.")
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
        monthly_df = self.df.groupby("Month").agg({
            "Machine Capacity": "mean",
            "Week": "max",
            **{col: "mean" for col in self.base_cols + ["Sum of Used Machine", "Average Usage", "Peak Usage", "Average Usage Ratio", "Peak Usage Ratio"] if col in self.df.columns},
            **{col: "mean" for col in self.df.columns if col.endswith("_Ratio") or col.endswith("_Share")}
        }).reset_index()
        monthly_df = monthly_df.sort_values(by="Week", ascending=False)
        monthly_df = monthly_df.fillna(0)
        return monthly_df

    def save_combined_html(self):
        if os.path.exists(self.base_weekly_file):
            df = pd.read_csv(self.base_weekly_file)
            df["Week"] = pd.to_datetime(df["Week"])
            df = df.sort_values(by="Week", ascending=True)
            df_table = df.sort_values(by="Week", ascending=False)
        else:
            print(f"Warning: No base weekly data found at {self.base_weekly_file}")
            return

        base_cols_cap = [col.capitalize() for col in self.base_cols]
        for col in ["Average Usage", "Peak Usage", "Average Usage Ratio", "Peak Usage Ratio"]:
            if col in self.config:
                if col == "Average Usage":
                    df[col] = df[base_cols_cap].mean(axis=1)
                    df_table[col] = df_table[base_cols_cap].mean(axis=1)
                elif col == "Peak Usage":
                    df[col] = df[base_cols_cap].max(axis=1)
                    df_table[col] = df_table[base_cols_cap].max(axis=1)
                elif col == "Average Usage Ratio":
                    df[col] = df["Average Usage"] / df["Machine Capacity"]
                    df_table[col] = df_table["Average Usage"] / df_table["Machine Capacity"]
                elif col == "Peak Usage Ratio":
                    df[col] = df["Peak Usage"] / df["Machine Capacity"]
                    df_table[col] = df_table["Peak Usage"] / df_table["Machine Capacity"]

        for col, config in self.config.items():
            if "{col}" in col:
                for base_col in base_cols_cap:
                    actual_col = col.replace("{col}", base_col)
                    equation = config["equation"].replace("{col}", base_col)
                    if "Machine Capacity" in equation:
                        df[actual_col] = df[base_col] / df["Machine Capacity"]
                        df_table[actual_col] = df_table[base_col] / df_table["Machine Capacity"]
                    elif "Sum of Used Machine" in equation:
                        df[actual_col] = df[base_col] / df["Sum of Used Machine"]
                        df_table[actual_col] = df_table[base_col] / df_table["Sum of Used Machine"]
        df = df.fillna(0)
        df_table = df_table.fillna(0)

        usage_cols = base_cols_cap
        sorted_cols = df[usage_cols].mean().sort_values(ascending=False).index.tolist()

        fig = make_subplots(rows=2, cols=1,
                            subplot_titles=("Machine Capacity Usage Trend", "Individual Machine Usage Breakdown"),
                            specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
                            vertical_spacing=0.2)

        fig.add_trace(go.Bar(x=df["Week"], y=df["Sum of Used Machine"], name="Sum of Used Machine", marker_color="blue"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["Week"], y=df["Average Usage"], name="Average Usage", mode="lines", line=dict(color="red")), row=1, col=1)

        colors = px.colors.qualitative.Plotly
        for i, col in enumerate(sorted_cols):
            fig.add_trace(go.Bar(x=df["Week"], y=df[col], name=f"{col} Usage", marker_color=colors[i % len(colors)]), row=2, col=1)
            fig.add_trace(go.Scatter(x=df["Week"], y=df[col], name=f"{col} Usage Line", mode="lines", line=dict(color=colors[i % len(colors)], dash="dash"), showlegend=False), row=2, col=1)

        fig.update_layout(
            height=1000,
            width=None,
            autosize=True,
            title_text="Machine Usage Trends (2022-2025)",
            barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
            showlegend=True,
            margin=dict(l=50, r=50, t=100, b=150)
        )
        fig.update_yaxes(title_text="Usage", row=1, col=1)
        fig.update_yaxes(title_text="Usage", row=2, col=1)
        fig.update_xaxes(
            title_text="Year-Week",
            tickangle=45,
            tickmode="auto",
            nticks=20,
            row=1, col=1
        )
        fig.update_xaxes(
            title_text="Year-Week",
            tickangle=45,
            tickmode="auto",
            nticks=20,
            row=2, col=1
        )

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
                h1, h2 {{ text-align: center; }}
                .table {{ width: 100%; border-collapse: collapse; margin-top: 60px; }}
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
            <h2>TM-Usage Data Table (All Weeks with Calculations)</h2>
            {html_table}
        </body>
        </html>
        """

        with open(self.html_combined_file, "w") as f:
            f.write(html_content)

    def save_heatmap_html(self):
        if os.path.exists(self.base_weekly_file):
            df = pd.read_csv(self.base_weekly_file)
            df["Week"] = pd.to_datetime(df["Week"])
            df = df.sort_values(by="Week", ascending=True)
        else:
            print(f"Warning: No base weekly data found at {self.base_weekly_file}")
            return

        base_cols_cap = [col.capitalize() for col in self.base_cols]
        df = df.fillna(0)

        heatmap_data = df[base_cols_cap].div(df["Sum of Used Machine"], axis=0).fillna(0) * 100

        fig = go.Figure(data=go.Heatmap(
            x=df["Week"],
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
            margin=dict(l=50, r=50, t=100, b=100)
        )
        fig.update_xaxes(
            title_text="Year-Week",
            tickangle=45,
            tickmode="auto",
            nticks=20
        )
        fig.update_yaxes(title_text="Machine")

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
                h1 {{ text-align: center; }}
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
            stacked_weekly_df = pd.read_csv(self.base_weekly_file)
            stacked_weekly_df["Week"] = pd.to_datetime(stacked_weekly_df["Week"])
            print(f"Debug: Loaded base_weekly_df columns: {list(stacked_weekly_df.columns)}")
        else:
            stacked_weekly_df = pd.DataFrame(columns=self.default_cols)
            print(f"Debug: Initialized base_weekly_df columns: {list(stacked_weekly_df.columns)}")

        if self.df is not None:
            common_cols_weekly = list(set(self.df.columns) & set(stacked_weekly_df.columns))
            if not common_cols_weekly:
                common_cols_weekly = self.default_cols
                stacked_weekly_df = pd.DataFrame(columns=common_cols_weekly)
            updated_weekly_df = pd.concat([self.df[common_cols_weekly], stacked_weekly_df[~stacked_weekly_df["Week"].isin(self.df["Week"])][common_cols_weekly]], ignore_index=True)
            for col in self.default_cols:
                if col not in updated_weekly_df.columns:
                    updated_weekly_df[col] = None
            updated_weekly_df = updated_weekly_df[self.default_cols + [col for col in updated_weekly_df.columns if col not in self.default_cols]]
            updated_weekly_df = updated_weekly_df.sort_values(by="Week", ascending=False)
            updated_weekly_df = updated_weekly_df.fillna(0)
            updated_weekly_df.to_csv(self.base_weekly_file, index=False)

        if self.df is not None:
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

    def process(self):
        if self.csv_file:
            self.load_and_convert_data()
        else:
            self.generate_random_data()
        self.calculate_columns()
        self.save_combined_html()
        self.save_heatmap_html()
        self.update_excel_sheet()

if __name__ == "__main__":
    base_weekly_file = "./base_dataset/1_base_weekly_machine_usage_dataset_calc.csv"

#   processor_test1 = DataProcessor(output_dir="OUTPUT_MUT_TEST_STEP1", base_weekly_file=base_weekly_file)
#   processor_test1.generate_random_data(weeks=20, base_cols="A:P")
#   processor_test1.output_weekly_csv_file = os.path.join(processor_test1.output_dir, "20w_weekly_data.csv")
#   processor_test1.output_csv_file = os.path.join(processor_test1.output_dir, "20w_monthly_data.csv")
#   processor_test1.process()
#
#   processor_test2 = DataProcessor(csv_file=os.path.join("OUTPUT_MUT_TEST_STEP1", "20w_weekly_data.csv"), output_dir="OUTPUT_MUT_TEST_STEP2", base_weekly_file=base_weekly_file)
#   processor_test2.generate_random_data(weeks=2, base_cols="A:P")
#   processor_test2.output_weekly_csv_file = os.path.join(processor_test2.output_dir, "2w_weekly_data.csv")
#   processor_test2.output_csv_file = os.path.join(processor_test2.output_dir, "22w_monthly_data.csv")
#   processor_test2.process()
#
#   processor_test3 = DataProcessor(csv_file=os.path.join("OUTPUT_MUT_TEST_STEP2", "2w_weekly_data.csv"), output_dir="OUTPUT_MUT_TEST_STEP3", base_weekly_file=base_weekly_file)
#   processor_test3.generate_random_data(weeks=1, base_cols="A:P")
#   processor_test3.output_weekly_csv_file = os.path.join(processor_test3.output_dir, "1w_weekly_data.csv")
#   processor_test3.output_csv_file = os.path.join(processor_test3.output_dir, "23w_monthly_data.csv")
#   processor_test3.process()

    processor_big = DataProcessor(output_dir="OUTPUT_MUT_TEST_BIG", base_weekly_file=base_weekly_file)
    processor_big.generate_all_weeks_data(start_date="2022-01-01", end_date="2025-03-31", base_cols="A:P")
    processor_big.output_weekly_csv_file = os.path.join(processor_big.output_dir, "all_weeks_weekly_data.csv")
    processor_big.output_csv_file = os.path.join(processor_big.output_dir, "all_weeks_monthly_data.csv")
    processor_big.process()

    print(f"SMALL_TEST 1: 20주 주간 데이터가 OUTPUT_MUT_TEST_STEP1/20w_weekly_data.csv에 저장되었습니다.")
    print(f"SMALL_TEST 1: 월별 데이터가 OUTPUT_MUT_TEST_STEP1/20w_monthly_data.csv에 저장되었습니다.")
    print(f"SMALL_TEST 2: 2주 주간 데이터가 OUTPUT_MUT_TEST_STEP2/2w_weekly_data.csv에 저장되었습니다.")
    print(f"SMALL_TEST 2: 월별 데이터가 OUTPUT_MUT_TEST_STEP2/22w_monthly_data.csv에 저장되었습니다.")
    print(f"SMALL_TEST 3: 1주 주간 데이터가 OUTPUT_MUT_TEST_STEP3/1w_weekly_data.csv에 저장되었습니다.")
    print(f"SMALL_TEST 3: 월별 데이터가 OUTPUT_MUT_TEST_STEP3/23w_monthly_data.csv에 저장되었습니다.")
    print(f"BIG_TEST: Group 1 주간 데이터가 OUTPUT_MUT_TEST_BIG/group1_weekly_data.csv에 저장되었습니다.")
    print(f"BIG_TEST: Group 2 주간 데이터가 OUTPUT_MUT_TEST_BIG/group2_weekly_data.csv에 저장되었습니다.")
    print(f"BIG_TEST: Group 3 주간 데이터가 OUTPUT_MUT_TEST_BIG/group3_weekly_data.csv에 저장되었습니다.")
    print(f"BIG_TEST: 병합 월별 데이터가 OUTPUT_MUT_TEST_BIG/all_weeks_monthly_data.csv에 저장되었습니다.")
    print(f"모든 주간 데이터가 {base_weekly_file}에 누적되었습니다.")
    print(f"결합된 HTML 파일이 각 출력 디렉토리의 'report_monthly_machine_usage_trend.html'에 저장되었습니다.")
    print(f"히트맵 HTML 파일이 각 출력 디렉토리의 'report_monthly_machine_usage_share_heatmap.html'에 저장되었습니다.")
