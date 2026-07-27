from .styles import STYLES, apply_cell
from .utils import default_visible_page, write_row, style_row, set_widths, is_date, set_dynamic_row_height


def render_plan(wb, plan):
    ws = wb.create_sheet(plan.sheet_name[:31])
    default_visible_page(ws)
    if plan.plan_type == 'daily':
        set_widths(ws, {'A':22,'B':16,'C':10,'D':46,'E':76,'F':84})
        width_map = {1:22,2:16,3:10,4:46,5:76,6:84}
        ws.freeze_panes = 'A15'
    else:
        set_widths(ws, {'A':11,'B':40,'C':76,'D':60,'E':70})
        width_map = {1:11,2:40,3:76,4:60,5:70}
    ws.cell(1,1,plan.title)
    style_row(ws,1,1,len(plan.headers),'plan_title')
    ws.row_dimensions[1].height = 24
    ws.cell(2,1,plan.subtitle)
    style_row(ws,2,1,len(plan.headers),'subtitle')
    write_row(ws,4,plan.headers,'plan_header')
    ws.row_dimensions[4].height = 30
    for i, vals in enumerate(plan.rows, start=5):
        set_dynamic_row_height(ws, i, vals, width_map, min_height=32, max_height=120)
        is_holiday = any(isinstance(x,str) and ('HOLIDAY' in x.upper() or x == 'Weekend') for x in vals)
        for c, val in enumerate(vals,1):
            ws.cell(i,c,val)
            if plan.plan_type == 'daily':
                if c == 1 and is_date(val):
                    apply_cell(ws.cell(i,c), STYLES['holiday_date'] if is_holiday else (STYLES['date'] if i % 2 else STYLES['body_center_gray']))
                elif c in [4,5,6]:
                    apply_cell(ws.cell(i,c), STYLES['holiday_left'] if is_holiday else (STYLES['body_left_gray'] if i % 2 == 0 else STYLES['body_left']))
                else:
                    apply_cell(ws.cell(i,c), STYLES['holiday_center'] if is_holiday else (STYLES['body_center_gray'] if i % 2 == 0 else STYLES['body_center']))
            else:
                apply_cell(ws.cell(i,c), STYLES['body_left'] if c > 1 else STYLES['body_center'])
    return ws
