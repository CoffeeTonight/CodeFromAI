import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import openpyxl
import json
from openpyxl import load_workbook
import os
import random
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
            default_df = pd.DataFrame(columns=["Week", "Sum of Used Machine"])
            default_df.to_csv(self.base_weekly_file, index=False)
            print(f"Created empty base weekly file: {self.base_weekly_file}")
        if not os.path.exists(self.base_monthly_file):
            default_df = pd.DataFrame(columns=["Year-Month", "Machine Capacity", "Week"])
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

    def _create_minimal_config(self):
        config = {
            "Peak Used Machine": {"type": "equation", "equation": "MAX({base_cols})"},
            "Average Used Machine": {"type": "equation", "equation": "Sum of Used Machine / Machine Capacity * 100"},
            "{col}_Ratio": {"type": "equation", "equation": "{col} / Machine Capacity"},
            "{col}_Share": {"type": "equation", "equation": "{col} / Sum of Used Machine"}
        }
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=4)
        return config

    def generate_all_weeks_data(self, start_date="2022-01-01", end_date="2025-03-31", base_cols="A:G"):
        fruit_names = ["Apple", "Banana", "Cherry", "Dragonfruit", "Elderberry", "Fig", "Grape"]
        self.base_cols = fruit_names

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
        }
        for col in self.base_cols:
            data[col] = [0.0] * len(weeks_list)

        peak_indices = list(range(len(self.base_cols)))
        random.shuffle(peak_indices)
        peak_indices = peak_indices * (len(weeks_list) // len(self.base_cols) + 1)
        peak_indices = peak_indices[:len(weeks_list)]

        for i, week in enumerate(weeks_list):
            active_cols = self.base_cols
            peak_idx = peak_indices[i]
            target_sum = random.uniform(30, 56)  # Sum of Used Machine range
            peak_value = target_sum * 0.7
            data[active_cols[peak_idx]][i] = round(peak_value, 1)
            remaining_sum = target_sum - peak_value

            non_peak_cols = [col for j, col in enumerate(active_cols) if j != peak_idx]
            for col in non_peak_cols:
                value = remaining_sum / len(non_peak_cols)
                data[col][i] = round(value, 1)
                remaining_sum -= value

        df = pd.DataFrame(data)
        df["Week"] = df["Week"].apply(lambda x: pd.to_datetime(f"{x.split('-')[0]}-W{x.split('-')[1].replace('W', '')}-1", format="%Y-W%W-%w"))
        df["Sum of Used Machine"] = df[self.base_cols].sum(axis=1)
        df = df[["Week"] + self.base_cols + ["Sum of Used Machine"]]
        df = df.sort_values(by="Week", ascending=False)
        self.df = df
        self.df.to_csv(self.output_weekly_csv_file, index=False)

    def load_and_convert_data(self):
        if not self.csv_file or not os.path.exists(self.csv_file):
            print(f"Warning: CSV file '{self.csv_file}' not found or not provided. Generating test data.")
            self.generate_all_weeks_data()
            return
        df = pd.read_csv(self.csv_file)
        df.columns = [col.lower().strip() for col in df.columns]

        fruit_names = ["apple", "banana", "cherry", "dragonfruit", "elderberry", "fig", "grape"]
        self.base_cols = [col for col in df.columns if col in fruit_names]
        if not self.base_cols:
            print(f"Warning: No fruit-named columns found in {self.csv_file}. Using heuristic detection.")
            self.base_cols = [col for col in df.columns if col not in ["year-month", "week"] and not col.startswith(("sum", "total"))]

        sum_col = next((col for col in df.columns if col.startswith("sum") or col.startswith("total")), None)
        if not sum_col:
            print(f"Warning: No 'sum' or 'total' column found. Calculating sum from items.")
            df["sum of used machine"] = df[self.base_cols].sum(axis=1)
            sum_col = "sum of used machine"

        required_cols = ["year-month", "week"] + self.base_cols + [sum_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Error: Missing columns {missing_cols}. Aborting.")
            return

        df["week"] = pd.to_datetime(df["week"])
        df["year-month"] = df["week"].dt.to_period("M").astype(str)
        df["machine capacity"] = df["year-month"].apply(lambda x: 32 if x < "2023-01" else 64)
        self.df = df[["year-month", "machine capacity", "week"] + self.base_cols + [sum_col]]
        self.df.columns = ["Year-Month", "Machine Capacity", "Week"] + [col.capitalize() for col in self.base_cols] + ["Sum of Used Machine"]
        self.df = self.df.sort_values(by="Week", ascending=False)
        self.df.to_csv(self.output_weekly_csv_file, index=False)

    def calculate_columns(self):
        if self.df is None:
            return
        base_cols_cap = [col.capitalize() for col in self.base_cols]
        print(f"Debug: DataFrame columns before calculation: {list(self.df.columns)}")

        self.df["Average Used Machine"] = (self.df["Sum of Used Machine"] / self.df["Machine Capacity"]) * 100
        self.df["Peak Used Machine"] = self.df[base_cols_cap].max(axis=1)

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
            "Average Used Machine": "mean",
            "Peak Used Machine": "max",
        }
        for col in self.base_cols:
            col_cap = col.capitalize()
            if col_cap in self.df.columns:
                agg_dict[col_cap] = "mean"

        monthly_df = self.df.groupby("Year-Month").agg(agg_dict).reset_index()
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

        df["X_Axis"] = df["Year-Month"]

        latest_idx = len(df) - 1

        # First Graph
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=df["X_Axis"], y=df["Sum of Used Machine"], name="Sum of Machine Operation",
                              marker_color="blue"))
        fig1.add_trace(go.Scatter(x=df["X_Axis"], y=df["Machine Capacity"], name="Machine Capacity", mode="lines",
                                  line=dict(color="green", dash="dot")))

        colors = px.colors.qualitative.Plotly
        for i, col in enumerate(base_cols_cap):
            if col in df.columns:
                ratio_values = (df[col] / df["Machine Capacity"]) * 100
                fig1.add_trace(go.Scatter(x=df["X_Axis"], y=ratio_values, name=f"{col} (%)", mode="lines",
                                          line=dict(color=colors[i % len(colors)]), opacity=0.5, yaxis="y2"))

        middle_idx = len(df) // 2
        latest_capacity = df["Machine Capacity"].iloc[latest_idx]
        fig1.add_annotation(x=df["X_Axis"].iloc[middle_idx], y=latest_capacity,
                            text=f"Capacity: {latest_capacity:.0f}ea",
                            showarrow=False, yshift=10, font=dict(size=20, color="green"))

        max_x = df["X_Axis"].iloc[-1]
        if latest_idx is not None:
            value = df["Sum of Used Machine"].iloc[latest_idx]
            fig1.add_annotation(x=max_x, y=value, text=f"Latest: {value:.1f}",
                                showarrow=True, ax=20, ay=0, xshift=40, xanchor="left", font=dict(size=16),
                                arrowhead=2, arrowsize=1, arrowwidth=1.5)

        fig1.update_layout(
            height=700,
            width=1600,
            title_text="Machine Usage Trend",
            title_font_size=24,
            bargap=0.2,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,
                xanchor="center",
                x=0.5,
                font=dict(size=20),
                tracegroupgap=10,
                itemsizing='constant',
                groupclick="toggleitem",
                title=""
            ),
            font=dict(size=20),
            margin=dict(l=100, r=200, t=100, b=150),
            yaxis=dict(title=dict(text="Sum of Machine Operation", font=dict(size=20)), tickfont=dict(size=20)),
            yaxis2=dict(
                title=dict(text="Usage Ratio (%)", font=dict(size=20)),
                tickfont=dict(size=20),
                range=[0, 100],
                overlaying='y',
                side='right',
                tickmode="linear",
                tick0=0,
                dtick=10,
                tickformat=".0f%"
            ),
            xaxis=dict(title="", tickfont=dict(size=20), tickangle=45)
        )

        # Second Graph
        fig2 = go.Figure()
        colors = px.colors.qualitative.Plotly
        for i, col in enumerate(base_cols_cap):
            if col in df.columns:
                bar_color = colors[i % len(colors)]
                fig2.add_trace(go.Bar(x=df["X_Axis"], y=df[col], name=f"{col}", marker_color=bar_color))
                fig2.add_trace(go.Scatter(x=df["X_Axis"], y=df[col], mode="lines", line=dict(color=bar_color, dash="dash", width=3),
                                          opacity=0.7, showlegend=False))
                ratio_values = (df[col] / df["Machine Capacity"]) * 100
                fig2.add_trace(go.Scatter(x=df["X_Axis"], y=ratio_values, mode="lines", line=dict(color=bar_color, width=3),
                                          opacity=0.5, showlegend=False, yaxis="y2"))

        total_items_2nd = len(base_cols_cap)
        rows_needed_2nd = (total_items_2nd + 4) // 5

        fig2.update_layout(
            height=700,
            width=1600,
            title_text="Machine Usage Trend Breakdown",
            title_font_size=24,
            barmode="stack",
            bargap=0.2,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15 - (rows_needed_2nd - 1) * 0.05,
                xanchor="center",
                x=0.5,
                font=dict(size=20),
                tracegroupgap=10,
                itemsizing='constant',
                groupclick="toggleitem",
                title=""
            ),
            font=dict(size=20),
            margin=dict(l=100, r=200, t=100, b=150 + rows_needed_2nd * 50),
            yaxis=dict(title=dict(text="Average Machine Usage", font=dict(size=20)), tickfont=dict(size=20)),
            yaxis2=dict(title=dict(text="Usage Ratio (%)", font=dict(size=20)), tickfont=dict(size=20), range=[0, 100], overlaying='y', side='right'),
            xaxis=dict(title="", tickfont=dict(size=20), tickangle=45)
        )

        # Convert figures to HTML
        graph1_html = fig1.to_html(full_html=False, include_plotlyjs="cdn")
        graph2_html = fig2.to_html(full_html=False, include_plotlyjs=False)

        # Combined HTML with updated table
        df_table = df_table.rename(columns={"Month": "Year-Month"})
        df_table = df_table.drop(columns=["Average Usage"], errors="ignore")
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Machine Usage Trends and Data</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ text-align: center; font-size: 20px; }}
                .table {{ width: 100%; border-collapse: collapse; margin-top: 60px; font-size: 20px; }}
                .table th, .table td {{ padding: 8px; text-align: left; }}
                .table-striped tbody tr:nth-child(odd) {{ background-color: #f2f2f2; }}
                .graph-container {{ margin-top: 40px; width: 90vw; max-width: 1600px; margin-left: auto; margin-right: auto; margin-bottom: 60px; }}
            </style>
        </head>
        <body>
            <h1>Machine Usage Trends and Data (2022-2025)</h1>
            <div class="graph-container">
                {graph1_html}
            </div>
            <div class="graph-container">
                {graph2_html}
            </div>
            <h2>TM-Usage Data Table (Monthly Calculations)</h2>
            {df_table.to_html(index=False, classes="table table-striped", border=0)}
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
            print(f"Warning: No machine columns (e.g., Apple, Banana) found in {self.base_monthly_file}. Heatmap cannot be generated.")
            return

        df = df.fillna(0)
        heatmap_data = df[base_cols_cap].div(df["Sum of Used Machine"], axis=0).fillna(0) * 100

        df["X_Axis"] = df["Year-Month"]
        fig = go.Figure(data=go.Heatmap(
            x=df["X_Axis"],
            y=base_cols_cap,
            z=heatmap_data.T,
            colorscale="Viridis",
            name="Usage Share (%)",
            showscale=True
        ))

        fig.update_layout(
            height=1200,
            width=1600,
            autosize=False,
            title_text="Machine Usage Share Heatmap (2022-2025)",
            title_font_size=24,
            margin=dict(l=100, r=200, t=150, b=150),
            font=dict(size=20)
        )
        fig.update_xaxes(
            title_text="",
            tickfont=dict(size=20),
            tickangle=45,
            tickmode="auto",
            nticks=20
        )
        fig.update_yaxes(
            title_text="Fruit",
            title=dict(font=dict(size=20)),
            tickfont=dict(size=20)
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
                h1 {{ text-align: center; font-size: 20px; }}
                .graph-container {{ width: 90vw; max-width: 1600px; margin-left: auto; margin-right: auto; margin-bottom: 60px; }}
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

    def process(self):
        self.load_and_convert_data()
        if self.df is not None:
            self.calculate_columns()
            self.update_excel_sheet()
            self.update_base_monthly()
            self.save_combined_html()
            self.save_heatmap_html()

    def update_excel_sheet(self):
        if os.path.exists(self.base_weekly_file):
            base_weekly_df = pd.read_csv(self.base_weekly_file)
            base_weekly_df["Week"] = pd.to_datetime(base_weekly_df["Week"])
            print(f"Debug: Loaded base_weekly_df columns: {list(base_weekly_df.columns)}")
        else:
            base_weekly_df = pd.DataFrame(columns=["Year-Month", "Machine Capacity", "Week", "Sum of Used Machine"])
            print(f"Debug: Initialized base_weekly_df columns: {list(base_weekly_df.columns)}")

        if self.df is not None:
            common_cols_weekly = list(set(self.df.columns) & set(base_weekly_df.columns))
            if not common_cols_weekly:
                common_cols_weekly = ["Year-Month", "Machine Capacity", "Week", "Sum of Used Machine"]
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
        else:
            print(f"Warning: No base weekly data found at {self.base_weekly_file}")
            return

        self.df = weekly_df
        self.calculate_columns()
        monthly_df = self.convert_to_monthly()

        if os.path.exists(self.base_monthly_file):
            existing_monthly_df = pd.read_csv(self.base_monthly_file)
        else:
            existing_monthly_df = pd.DataFrame(columns=["Year-Month", "Machine Capacity", "Week"])

        new_months = set(monthly_df["Year-Month"])
        unchanged_months_df = existing_monthly_df[~existing_monthly_df["Year-Month"].isin(new_months)]
        updated_monthly_df = pd.concat([unchanged_months_df, monthly_df], ignore_index=True)
        updated_monthly_df = updated_monthly_df.sort_values(by="Week", ascending=False)
        updated_monthly_df = updated_monthly_df.fillna(0)
        updated_monthly_df.to_csv(self.base_monthly_file, index=False)
        print(f"Updated base monthly dataset: {self.base_monthly_file}")

def test_real_set(base_weekly_file):
    print("\nRunning Real Set Test (Big Test)")

    output_dir = "OUTPUT_TEST_BIG"
    dummy_file = os.path.join(output_dir, "big_test_weekly_data.csv")

    processor = DataProcessor(output_dir=output_dir, base_weekly_file=base_weekly_file)
    processor.generate_all_weeks_data(start_date="2022-01-01", end_date="2025-03-31")
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
        test_real_set(base_weekly_file)
        print(f"\nAll test data accumulated in {base_weekly_file}")
        print(f"Base monthly data updated in {base_monthly_file}")
        print("Test results saved in OUTPUT_TEST*/ directories")


