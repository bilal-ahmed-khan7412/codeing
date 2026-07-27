from pathlib import Path
from openpyxl import Workbook
from tracker_excel.renderer.parser import parse_workbook, WorkbookData
from tracker_excel.renderer.plan_renderer import render_plan
from tracker_excel.renderer.intern_renderer import render_intern
from tracker_excel.renderer.dashboard_renderer import render_dashboard
from tracker_excel.renderer.hidden_renderer import render_hidden_sheets

class RenderService:
    @staticmethod
    def render_data(data: WorkbookData, output_path: str) -> str:
        wb = Workbook()
        wb.remove(wb.active)
        for plan in data.plans:
            render_plan(wb, plan)
        intern_meta = []
        for intern in data.interns:
            intern_meta.append(render_intern(wb, intern))
        render_dashboard(wb, intern_meta)
        render_hidden_sheets(wb, data, intern_meta)
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        wb.save(output_path)
        return output_path

    @staticmethod
    def render_from_workbook(source_path: str, output_path: str) -> str:
        data = parse_workbook(source_path)
        return RenderService.render_data(data, output_path)
