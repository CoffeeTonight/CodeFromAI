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
    def __init__(self, csv_file=None, output_dir="OUTPUT_MUT_TEST_STEP1", stacked_weekly_file="stacked_weekly_data.csv"):
        self.csv_file = csv_file
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.stacked_weekly_file = stacked_weekly_file
        self.output_csv_file = os.path.join(self.output_dir, "monthly_data.csv")
        self.output_weekly_csv_file = os.path.join(self.output_dir, "weekly_data.csv")
        self.output_calculated_csv_file = os.path.join(self.output_dir, "calculated_weekly_data.csv")
        self.excel_file = os.path.join(self.output_dir, "output_interactive.xlsx")
        self.config_file = os.path.join(self.output_dir, "equation_config.json")
        self.html_graph_file = os.path.join(self.output_dir, "trend_graph.html")
        self.html_table_file = os.path.join(self.output_dir, "table.html")
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
        self.df = self.df.fillna(0)  # NaN을 0으로 대체
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
        weeks_list = sorted(list(set(weeks_list)))  # 중복 제거

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
        df = df[["Month", "Machine Capacity", "Week"] + self.base_cols + ["Sum of Used Machine"]]
        df = df.fillna(0)  # NaN을 0으로 대체
        df = df.sort_values(by="Week", ascending=False)

        # 3개 그룹으로 분할, 마지막 주가 월 중간에 끝나도록 설정
        group1_end = pd.to_datetime("2023-01-16")  # 1월 3주차 (월 중간)
        group2_end = pd.to_datetime("2024-02-12")  # 2월 2주차 (월 중간)

        group1 = df[df["Week"] <= group1_end]
        group2 = df[(df["Week"] > group1_end) & (df["Week"] <= group2_end)]
        group3 = df[df["Week"] > group2_end]

        # 각 그룹 저장
        group1.to_csv(os.path.join(self.output_dir, "group1_weekly_data.csv"), index=False)
        group2.to_csv(os.path.join(self.output_dir, "group2_weekly_data.csv"), index=False)
        group3.to_csv(os.path.join(self.output_dir, "group3_weekly_data.csv"), index=False)

        # 병합 데이터로 self.df 설정 (주간 데이터 유지)
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
        self.df = self.df.fillna(0)  # NaN을 0으로 대체
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

        self.df = self.df.fillna(0)  # 계산 후 NaN을 0으로 대체
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
        monthly_df = monthly_df.fillna(0)  # NaN을 0으로 대체
        return monthly_df

    def plot_graph_to_html(self):
        # 누적 주간 데이터 로드
        if os.path.exists(self.stacked_weekly_file):
            df = pd.read_csv(self.stacked_weekly_file)
            df["Week"] = pd.to_datetime(df["Week"])
            df = df.sort_values(by="Week", ascending=True)  # 시간순 정렬
        else:
            print(f"Warning: No stacked weekly data found at {self.stacked_weekly_file}")
            return

        # 계산 열 추가
        base_cols_cap = [col.capitalize() for col in self.base_cols]
        for col in ["Average Usage", "Peak Usage", "Average Usage Ratio", "Peak Usage Ratio"]:
            if col in self.config:
                if col == "Average Usage":
                    df[col] = df[base_cols_cap].mean(axis=1)
                elif col == "Peak Usage":
                    df[col] = df[base_cols_cap].max(axis=1)
                elif col == "Average Usage Ratio":
                    df[col] = df["Average Usage"] / df["Machine Capacity"]
                elif col == "Peak Usage Ratio":
                    df[col] = df["Peak Usage"] / df["Machine Capacity"]

        for col, config in self.config.items():
            if "{col}" in col:
                for base_col in base_cols_cap:
                    actual_col = col.replace("{col}", base_col)
                    equation = config["equation"].replace("{col}", base_col)
                    if "Machine Capacity" in equation:
                        df[actual_col] = df[base_col] / df["Machine Capacity"]
                    elif "Sum of Used Machine" in equation:
                        df[actual_col] = df[base_col] / df["Sum of Used Machine"]
        df = df.fillna(0)

        # A~P 사용량 정렬 (내림차순)
        usage_cols = base_cols_cap
        sorted_cols = df[usage_cols].mean().sort_values(ascending=False).index.tolist()

        # 서브플롯 생성 (3행: Graph 1, Graph 2, 추가 제안)
        fig = make_subplots(rows=3, cols=1,
                            subplot_titles=("Machine Capacity Usage Trend", "Individual Machine Usage Breakdown", "Machine Usage Share Heatmap"),
                            specs=[[{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]],
                            vertical_spacing=0.1)

        # Graph 1: Sum of Used Machine (막대) & Average Usage (선)
        fig.add_trace(go.Bar(x=df["Week"], y=df["Sum of Used Machine"], name="Sum of Used Machine", marker_color="blue"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["Week"], y=df["Average Usage"], name="Average Usage", mode="lines", line=dict(color="red")), row=1, col=1)

        # Graph 2: Stacked Bar (A~P 사용량) & Lines (A~P)
        colors = px.colors.qualitative.Plotly  # 색상 팔레트
        for i, col in enumerate(sorted_cols):
            fig.add_trace(go.Bar(x=df["Week"], y=df[col], name=f"{col} Usage", marker_color=colors[i % len(colors)]), row=2, col=1)
            fig.add_trace(go.Scatter(x=df["Week"], y=df[col], name=f"{col} Usage Line", mode="lines", line=dict(color=colors[i % len(colors)], dash="dash"), showlegend=False), row=2, col=1)

        # 추가 제안: Graph 3 - A~P 사용 비율 히트맵
        heatmap_data = df[base_cols_cap].div(df["Sum of Used Machine"], axis=0).fillna(0) * 100
        fig.add_trace(go.Heatmap(x=df["Week"], y=base_cols_cap, z=heatmap_data.T, colorscale="Viridis", name="Usage Share (%)", showscale=True), row=3, col=1)

        # 레이아웃 설정
        fig.update_layout(
            height=1200,
            width=1200,
            title_text="Machine Usage Trends (2022-2025)",
            barmode="stack",  # Graph 2는 누적 막대
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            showlegend=True
        )
        fig.update_yaxes(title_text="Usage", row=1, col=1)
        fig.update_yaxes(title_text="Usage", row=2, col=1)
        fig.update_yaxes(title_text="Machine", row=3, col=1)
        fig.update_xaxes(title_text="Year-Week", row=1, col=1)
        fig.update_xaxes(title_text="Year-Week", row=2, col=1)
        fig.update_xaxes(title_text="Year-Week", row=3, col=1)

        # HTML 파일로 저장
        fig.write_html(self.html_graph_file)

    def save_table_to_html(self):
        # 누적 주간 데이터 로드 및 계산
        if os.path.exists(self.stacked_weekly_file):
            df_to_save = pd.read_csv(self.stacked_weekly_file)
            df_to_save["Week"] = pd.to_datetime(df_to_save["Week"])
            df_to_save = df_to_save.sort_values(by="Week", ascending=False)
        else:
            print(f"Warning: No stacked weekly data found at {self.stacked_weekly_file}")
            return

        # 계산 열 추가
        base_cols_cap = [col.capitalize() for col in self.base_cols]
        for col in ["Average Usage", "Peak Usage", "Average Usage Ratio", "Peak Usage Ratio"]:
            if col in self.config:
                if col == "Average Usage":
                    df_to_save[col] = df_to_save[base_cols_cap].mean(axis=1)
                elif col == "Peak Usage":
                    df_to_save[col] = df_to_save[base_cols_cap].max(axis=1)
                elif col == "Average Usage Ratio":
                    df_to_save[col] = df_to_save["Average Usage"] / df_to_save["Machine Capacity"]
                elif col == "Peak Usage Ratio":
                    df_to_save[col] = df_to_save["Peak Usage"] / df_to_save["Machine Capacity"]

        for col, config in self.config.items():
            if "{col}" in col:
                for base_col in base_cols_cap:
                    actual_col = col.replace("{col}", base_col)
                    equation = config["equation"].replace("{col}", base_col)
                    if "Machine Capacity" in equation:
                        df_to_save[actual_col] = df_to_save[base_col] / df_to_save["Machine Capacity"]
                    elif "Sum of Used Machine" in equation:
                        df_to_save[actual_col] = df_to_save[base_col] / df_to_save["Sum of Used Machine"]
        df_to_save = df_to_save.fillna(0)

        html_table = df_to_save.to_html(index=False, classes="table table-striped", border=0)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TM-Usage Table</title>
            <style>
                .table {{ width: 100%; border-collapse: collapse; }}
                .table th, .table td {{ padding: 8px; text-align: left; }}
                .table-striped tbody tr:nth-child(odd) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>TM-Usage Data Table (All Weeks with Calculations)</h1>
            {html_table}
        </body>
        </html>
        """
        with open(self.html_table_file, "w") as f:
            f.write(html_content)

    def update_excel_sheet(self):
        if os.path.exists(self.stacked_weekly_file):
            stacked_weekly_df = pd.read_csv(self.stacked_weekly_file)
            stacked_weekly_df["Week"] = pd.to_datetime(stacked_weekly_df["Week"])
            print(f"Debug: Loaded stacked_weekly_df columns: {list(stacked_weekly_df.columns)}")
        else:
            stacked_weekly_df = pd.DataFrame(columns=self.default_cols)
            print(f"Debug: Initialized stacked_weekly_df columns: {list(stacked_weekly_df.columns)}")

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
            updated_weekly_df = updated_weekly_df.fillna(0)  # NaN을 0으로 대체
            updated_weekly_df.to_csv(self.stacked_weekly_file, index=False)

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
        self.plot_graph_to_html()
        self.save_table_to_html()
        self.update_excel_sheet()

if __name__ == "__main__":
    # 단일 주간 데이터 파일
    stacked_weekly_file = "stacked_weekly_data.csv"

    # SMALL_TEST
    processor_test1 = DataProcessor(output_dir="OUTPUT_MUT_TEST_STEP1", stacked_weekly_file=stacked_weekly_file)
    processor_test1.generate_random_data(weeks=20, base_cols="A:P")
    processor_test1.output_weekly_csv_file = os.path.join(processor_test1.output_dir, "20w_weekly_data.csv")
    processor_test1.output_csv_file = os.path.join(processor_test1.output_dir, "20w_monthly_data.csv")
    processor_test1.process()

    processor_test2 = DataProcessor(csv_file=os.path.join("OUTPUT_MUT_TEST_STEP1", "20w_weekly_data.csv"), output_dir="OUTPUT_MUT_TEST_STEP2", stacked_weekly_file=stacked_weekly_file)
    processor_test2.generate_random_data(weeks=2, base_cols="A:P")
    processor_test2.output_weekly_csv_file = os.path.join(processor_test2.output_dir, "2w_weekly_data.csv")
    processor_test2.output_csv_file = os.path.join(processor_test2.output_dir, "22w_monthly_data.csv")
    processor_test2.process()

    processor_test3 = DataProcessor(csv_file=os.path.join("OUTPUT_MUT_TEST_STEP2", "2w_weekly_data.csv"), output_dir="OUTPUT_MUT_TEST_STEP3", stacked_weekly_file=stacked_weekly_file)
    processor_test3.generate_random_data(weeks=1, base_cols="A:P")
    processor_test3.output_weekly_csv_file = os.path.join(processor_test3.output_dir, "1w_weekly_data.csv")
    processor_test3.output_csv_file = os.path.join(processor_test3.output_dir, "23w_monthly_data.csv")
    processor_test3.process()

    # BIG_TEST: 2022-2025.03을 3개 그룹으로 분할
    processor_big = DataProcessor(output_dir="OUTPUT_MUT_TEST_BIG", stacked_weekly_file=stacked_weekly_file)
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
    print(f"모든 주간 데이터가 {stacked_weekly_file}에 누적되었습니다.")





#   Graph is very good.
#'ll let you know what csv file should be exist. This is a clean-up the outputs.
#
#   given csv; 1_new_weekly_machine_usage.csv Maybe several test given csv have more free rule for naming.
#   all weekly maintained (stacked) csv after calculated; 2_all_weekly_usage_trend_calc.csv
#   all monthly calculated stacked csv using 2.'s csv. considering month merging with partial weeks.; 3_all_monthly_usage_trend_calc.csv
#   all_monthly_usage_trend.html/.vba/.xlsx
#   please merge table and graph into single html file.
