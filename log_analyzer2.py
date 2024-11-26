#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gzip
import os
import re
import statistics
import configparser
import sys
import argparse
import logging

# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

config = {
    "REPORT_SIZE": 100,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "LOG_FILE": None,
    "ERRORS_THRESHOLD": 10
}


def main(config: Cfg):
    """
    Основная координирующая функция работы скрипта
    
    parameters: 
    - config - словарь конфигурации
    - config_file - имя файла конфигурации
    """
    try:
        logging.info('select log to parse')
        log_dir = pathlib.Path(cast(str, config.get("LOG_DIR")))
        last_log = get_last_logfile(log_dir)
        if not last_log:
            logger.info(f"Nothing to do in '{log_dir}'!")
            return

        logging.info('checking reports')
        report_dir = pathlib.Path(cast(str, config.get("REPORT_DIR")))
        report_path = get_report_path(report_dir, last_log)
        if report_path.exists():
            logger.info(f"Report for '{last_log.path}' already present")
            return
            
            logging.info('rendering data....')
            log_stat = get_requests_lex(
                last_log, cast(float, config.get("ERRORS_THRESHOLD")), LogEntry())
            log_stat = sorted(log_stat, key=lambda w: w["time_sum"], reverse=True)
            log_stat = log_stat[: config.get("REPORT_SIZE")]  # cut report to REPORT_SIZE
            report_templ_path = report_dir / "report.html"
            create_report(report_templ_path, report_path, log_stat)

    # Перехват "неожиданных" ошибок и логирование их.
    except Exception as e:
        logging.exception(e, exc_info=True)     

def get_last_logfile(log_dir: pathlib.Path) -> Optional[Log]:
    if not log_dir.exists() or not log_dir.is_dir():
        raise FileNotFoundError("Log dir wrong path")

    logfile = None
    pattern = re.compile(r"nginx-access-ui\.log-(\d{8})(\.gz)?$")
    for path in log_dir.iterdir():
        try:
            [(date, ext)] = re.findall(pattern, str(path))
            ld = datetime.datetime.strptime(date, "%Y%m%d")
            log_date = ld.date()  # date from current file filename
            if not logfile or log_date > logfile.date:
                logfile = Log(path, log_date, ext)
        except ValueError:
            continue

    return logfile


def get_report_path(report_dir: pathlib.Path, log: Log):
    if not report_dir.exists() or not report_dir.is_dir():
        raise FileNotFoundError("Report dir wrong path")

    report_filename = f"report-{log.date:%Y.%m.%d}.html"
    report_path = report_dir / report_filename
    return report_path

def get_requests_lex(log, errors_level: float, entry):
    """
    Parse NGINX logfile using lexemes
    :param log: file to be parsed
    :param errors_level: errors threshold
    :param entry: field names class
    :return: dictionary with urls and stat
    """
    data = gzip.open(log.path.absolute(), mode="rt") if log.ext == ".gz" else log.path.open()

    lexer = Lexer(RULES)  # prepare lexemes

    lines = 0
    fails = 0
    urls_data: Dict[str, List[float]] = collections.defaultdict(list)
    with data:
        for line in data:  # reading file line by line
            lines += 1
            try:
                tokens = lexer(line)
            except ValueError:
                # logging.exception("Error in line '%s'", line)
                logger.info("Error in line '%s'", line)
                fails += 1
                continue  # fix error and continue

            process_tokens(tokens, entry)

            try:
                urls_data[entry.request.split()[1]].append(float(entry.request_time))
            except AttributeError:
                fails += 1
                continue

    errors = fails / lines * 100
    if errors > errors_level:
        raise ValueError(f"Ahtung! Errors % [{errors}] more than {errors_level}%!")

    return calculate_url_stat(urls_data)


RULES = [
    (r"\s+", WSP),
    (r'-|"-"', NO_DATA),
    (r'"([^"]+)"', QUOTED_STRING),
    (r"\[([^\]]+)\]", DATE),
    (r"([^\s]+)", RAW),
]


def create_report(
        template_path: pathlib.Path,
        dest_path: pathlib.Path,
        log_stat: List[Dict[str, Union[str, float]]],
):
    with template_path.open() as tp:
        template = string.Template(tp.read())
    report = template.safe_substitute(table_json=json.dumps(log_stat))
    with dest_path.open(mode="w") as dp:
        dp.write(report)

def parse_args():
    parser = argparse.ArgumentParser(
        "Parsing NGINX logs and reports creation tool v.1.0"
    )
    parser.add_argument("--config", dest="config_path", help="Settings file path")
    return parser.parse_args()

def get_config(path: str, def_cfg: Cfg):
    if not path:
        return def_cfg

    p = pathlib.Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError("Wrong settings file path")

    with p.open(encoding="utf-8") as data:
        conf_file = json.load(data)

    return {**def_cfg, **conf_file}

def setup_logging(logfile: Optional[str]):
    structlog.configure(
        processors=[
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M.%S", utc=False),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=(
            structlog.PrintLoggerFactory()
            if not logfile
            else structlog.WriteLoggerFactory(
                file=pathlib.Path(logfile).with_suffix(".log").open(mode="wt", encoding="utf-8")
            )
        ),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    log = structlog.get_logger()
    return log

    class LogEntry(object):
    FIELDS = (
        "remote_addr",
        "_skip",
        "remote_user",
        "time_local",
        "request",
        "status",
        "body_bytes_sent",
        "http_referer",
        "http_user_agent",
        "server_name",
        "custom_field_1",
        "custom_field_2",
        "request_time",
    )

def process_tokens(tokens, entry):
    """
    Process tokens and set attributes of the entry object.
    """
    field_idx = 0
    for re_match, token_type in tokens:
        if token_type == WSP:
            continue  # ignore spaces
        elif token_type == NO_DATA:
            value = None  # NO_DATA equal None
        elif token_type == RAW:
            value = re_match.group(1)
        elif token_type == QUOTED_STRING:
            value = re_match.group(1)
        elif token_type == DATE:
            value = datetime.datetime.strptime(
                re_match.group(1), "%d/%b/%Y:%H:%M:%S %z"
            )
        else:
            raise SyntaxError("Unknown token", token_type, re_match)
        field_name = LogEntry.FIELDS[field_idx]
        setattr(entry, field_name, value)  # equal to: entry.field_name = value
        field_idx += 1

def Lexer(rules):
    prepared = [(re.compile(regexp), token_type) for regexp, token_type in rules]

    def lex(line):
        line_len = len(line)  # log line length
        i = 0  # current position
        while i < line_len:
            for pattern, token_type in prepared:  # take regexps one by one
                match = pattern.match(line, i)  # is equal?
                if match is None:  # no - take next regexp
                    continue
                i = match.end()  # shift end pointer
                yield match, token_type  # return token
                break  # return to analise remain in string with new offset i

    return lex

def calculate_url_stat(urls_data):
    """
    Calculate statistics for each URL.
    """
    total_count = 0
    total_time = 0.0
    for request_times in urls_data.values():
        total_count += len(request_times)
        total_time += sum(request_times)

    stat = []
    for url, request_times in urls_data.items():
        stat.append(
            {
                "url": url,
                "count": len(request_times),
                "count_perc": round(100.0 * len(request_times) / float(total_count), 3),
                "time_sum": round(sum(request_times), 3),
                "time_perc": round(100.0 * sum(request_times) / total_time, 3),
                "time_avg": round(statistics.mean(request_times), 3),
                "time_max": round(max(request_times), 3),
                "time_med": round(statistics.median(request_times), 3),
            }
        )
    return stat

if __name__ == "__main__":
    args = parse_args()
    conf = get_config(args.config_path, config)
    logger = setup_logging(conf.get("LOG_FILE"))

    try:
        main(conf)
    except Exception as e:
        logger.info(str(e))
