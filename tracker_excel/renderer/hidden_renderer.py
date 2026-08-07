from datetime import datetime
from .utils import write_row
from .styles import STYLES, apply_cell

HIDDEN_SHEETS = ['_Config','_Interns','_Plans','_PlanItems','_Tasks','_Projects','_WeeklyReports','_Holidays','_Versions']


def render_hidden_sheets(wb, data, intern_meta, version_action='render', version_note=''):
    for name in HIDDEN_SHEETS:
        if name in wb.sheetnames:
            ws = wb[name]
        else:
            ws = wb.create_sheet(name)
        ws.sheet_state = 'hidden'

    ws = wb['_Config']
    write_row(ws,1,['Key','Value'],'table_header')
    rows = [
        ['schema_version','1.0'],
        ['renderer','Workbook Renderer v1'],
        ['source_model','original-workbook-compatible'],
        ['merged_cells_policy','none in generated visible sheets'],
    ]
    for r, vals in enumerate(rows,2): write_row(ws,r,vals,'body_left')

    ws = wb['_Interns']
    write_row(ws,1,['Intern','Sheet','TaskStart','TaskEnd','WeeklyStart','WeeklyEnd','ProjectStart','ProjectEnd','Weeks','TargetEnd'],'table_header')
    for r,m in enumerate(intern_meta,2):
        write_row(ws,r,[m['name'],m['sheet'],m['task_start'],m['task_end'],m['weekly_start'],m['weekly_end'],m['project_start'],m['project_end'],m['week_count'],m.get('target_end')],'body_left')

    ws = wb['_Plans']
    write_row(ws,1,['PlanSheet','PlanType','Title','Subtitle'],'table_header')
    for r,p in enumerate(data.plans,2): write_row(ws,r,[p.sheet_name,p.plan_type,p.title,p.subtitle],'body_left')

    ws = wb['_PlanItems']
    write_row(ws,1,['PlanSheet','RowNo','Col1','Col2','Col3','Col4','Col5','Col6'],'table_header')
    r = 2
    for p in data.plans:
        for i,row in enumerate(p.rows,1):
            write_row(ws,r,[p.sheet_name,i]+row,'body_left')
            r += 1

    ws = wb['_Tasks']
    write_row(ws,1,['Intern','RowNo','Date','Week','Theme','Task','Status','Remarks'],'table_header')
    r=2
    for intern in data.interns:
        for i,t in enumerate(intern.tasks,1):
            write_row(ws,r,[intern.name,i]+t,'body_left')
            r += 1

    ws = wb['_Projects']
    write_row(ws,1,['Intern','RowNo','#','Title','Description','AssignedDate','DueDate','Status'],'table_header')
    r=2
    for intern in data.interns:
        for i,p in enumerate(intern.projects,1):
            write_row(ws,r,[intern.name,i]+p,'body_left')
            r += 1

    ws = wb['_WeeklyReports']
    write_row(ws,1,['Intern','RowNo','Week','Theme','Highlights','Blockers','TasksCompletedFormula','ManagerComments','EmailSent','LMAcknowledged'],'table_header')
    r=2
    for intern in data.interns:
        for i,w in enumerate(intern.weekly_reports,1):
            write_row(ws,r,[intern.name,i]+w,'body_left')
            r += 1

    ws = wb['_Holidays']
    write_row(ws,1,['HolidayName','Date','Scope','Intern','RenderedAsScheduleRow'],'table_header')
    for r, h in enumerate(data.holidays, 2):
        write_row(ws, r, h, 'body_left')

    ws = wb['_Versions']
    write_row(ws,1,['Version','Action','Notes'],'table_header')
    for r, v in enumerate(data.versions, 2):
        write_row(ws, r, v, 'body_left')
    new_version = f'v{len(data.versions) + 1}'
    note = version_note or f'Rendered {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    write_row(ws, len(data.versions) + 2, [new_version, version_action, note], 'body_left')
