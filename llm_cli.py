
import argparse
from tracker_llm.planner import LLMPlanner
from tracker_commands.executor import CommandExecutor
from tracker_commands.validator import CommandValidationError


def main():
    parser = argparse.ArgumentParser(description="LLM command interface for Intern Tracker")
    parser.add_argument('prompt', help='Natural language instruction')
    parser.add_argument('--env', default='.env')
    parser.add_argument('--source')
    parser.add_argument('--workbook')
    parser.add_argument('--output')
    parser.add_argument('--execute', action='store_true', help='Execute the planned command')
    args = parser.parse_args()

    defaults = {}
    if args.source:
        defaults['source'] = args.source
    if args.workbook:
        defaults['workbook'] = args.workbook
    if args.output:
        defaults['output'] = args.output

    try:
        payload = LLMPlanner(args.env).plan(args.prompt, defaults)
        print('PLANNED_COMMAND_JSON=')
        print(payload)
        if args.execute:
            result = CommandExecutor().execute(payload)
            print(result.message)
            if result.output_path:
                print(result.output_path)
            if result.data.get('summary'):
                print(result.data['summary'])
    except CommandValidationError as e:
        print(f'MISSING_OR_INVALID_INFO: {e}')
        raise SystemExit(2)

if __name__ == '__main__':
    main()
