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
    "LOG_FILE":"my_super_log.log"
}


def main(config, config_file):
    """
    Основная координирующая функция работы скрипта
    
    parameters: 
    - config - словарь конфигурации
    - config_file - имя файла конфигурации
    """
    try:
        # Если указан лог-файл в конфиге, то логирование будет
        # производиться в это файл.
        if 'LOG_FILE' in config:
            log_file = config['LOG_FILE']
        else:
            log_file = None
        # Настраиваем конфигурацию для логирования. 
        logging.basicConfig(filename=log_file, filemode='w', 
                            level=logging.DEBUG, 
                            format='%(asctime)s - %(levelname)s - %(message)s', 
                            datefmt='%m/%d/%Y %I:%M:%S %p')

        logging.info('parse config file')
        config = read_config(config, config_file, logging)
        if config == False:
            return

        logging.info('select log to parse')
        file_params = get_last_file(config['LOG_DIR'], logging)
        if file_params == False:
            return

        logging.info('checking reports')
        if isset_report(config['REPORT_DIR'], str(file_params['date'])):
            logging.error('report already done')
            return

        logging.info('parsing log....')
        path_and_filename = config['LOG_DIR']+'/'+file_params['name']
        data, count, time = parse(read_file(path_and_filename, file_params['format']))

        logging.info('rendering data....')
        render_data = make_report(data, count, time, config['REPORT_SIZE'])

        logging.info('make report in .html')
        render_tpl(render_data, config['REPORT_DIR'], str(file_params['date']))
    # Перехват "неожиданных" ошибок и логирование их.
    except Exception as e:
        logging.exception(e, exc_info=True)
        


def read_config(config, config_file, logging):
    """
    Функция, которая считывает настройки конфигурации из файла, 
    путь до которого указывается в командной строке, также есть
    дефолный файл конфигурации. Функция сопоставляет с конфигурациями,
    указанными в самом скрипте и выдает в результате конфигурацию, у 
    которой в приоритете стоят данные из файла
    
    parameters: 
    - config - словарь конфигурации
    - config_file - имя файла конфигурации
    - logging - объект класса, предназначенного для логирования
    """
    if os.path.exists(config_file):
        config_parse = configparser.ConfigParser()
        config_parse.read(config_file)
        if config_parse.has_section('log_analyzer'):
            try:
                config['REPORT_SIZE'] = config_parse['log_analyzer']['REPORT_SIZE']
                logging.info('read "REPORT_SIZE" from file')
            except KeyError:
                logging.info('read "REPORT_SIZE" from config in script')
            try:
                config['REPORT_DIR'] = config_parse['log_analyzer']['REPORT_DIR']
                logging.info('read "REPORT_DIR" from file')
            except KeyError:
                logging.info('read "REPORT_DIR" from config in script')
            try:
                config['LOG_DIR'] = config_parse['log_analyzer']['LOG_DIR']
                logging.info('read "LOG_DIR" from file')
            except KeyError:
                logging.info('read "LOG_DIR" from config in script')
        else:
            logging.error('config file not parsed')
            return False
        return config
    else:
        if config_file == 'config.ini':
            logging.error('no default config file')
            return False
        else:
            logging.error('no such config file')
            return False

def parse(file_data):
    """
    Функция, которая парсит файл с логом сервера 
    
    parameters: 
    - file_data - имя файла для парсинга
    """
    count = 0
    count_index_error = 0
    time = float(0)
    all_data = {}
    # бесконечный цикл, пока генератор не выдаст ошибку StopIteration
    while True:
        # считает общее колличество запросов в логе
        count+=1
        try:
            # регулярное выражение для получения необходимых параметров из лога
            params = re.findall(r'\[([\s\S]+?)\] "[A-Z-]*? (.+?) [\s\S]+ ([\d\.]+?)\n', next(file_data))[0]
            # считает общее время запросов в логе
            time+=float(params[2])
            # проверяем, есть ли данные о таком запросе уже, 
            # если есть то дополняем их новыми
            if params[1] in all_data:
                all_data[params[1]][0] += 1
                all_data[params[1]][1] += float(params[2])
                all_data[params[1]][3].append(float(params[2]))
                if float(params[2]) > all_data[params[1]][2]:
                    all_data[params[1]][2] = float(params[2])
            # если данных о запросе еще нет, то создаем словарь,
            # ключем которого будет являться название запроса
            else:
                all_data[params[1]] = []
                all_data[params[1]].append(1)
                all_data[params[1]].append(float(params[2]))
                all_data[params[1]].append(float(params[2]))
                all_data[params[1]].append([])
                all_data[params[1]][3].append(float(params[2]))
        except StopIteration:
            break
        # Если выбросило ошибку IndexError, значит спарсить строку из лога
        # не удалось. Записываем количество неудачно спаршенных строк
        except IndexError:
            count_index_error+=1
    # Если количество неудачно спаршенных строк превышает 20 % от 
    # общего количества строк, то выходим с ошибкой и пишем ее в лог
    if round (count_index_error/count*100, 3) > 20:
        logging.error('cannot parse log, maybe log`s format was changed')
        return 
    return all_data, count, time


def make_report(not_render_data, count, time, report_size):
    """
    Функция, которая из полученных парсингом данных высчитывает 
    необходимые значения, собирает в словарь и сортирует данные. 
    
    parameters: 
    - not_render_data - не "отрендеренные" данные
    - count - общее количество запросов на сервер из лога
    - time - общее время запросов на сервер из лога
    - report_size - количесвто записей для вывода в таблицу отчета
      по наибольшему
    """
    return_data = []
    requests = not_render_data.keys()
    for request in requests:
        one_request_params = {}
        one_request_params['url'] = request
        one_request_params['count'] = not_render_data[request][0]
        one_request_params['time_sum'] = round(not_render_data[request][1], 3)
        one_request_params['time_max'] = not_render_data[request][2]
        one_request_params['count_perc'] = round(not_render_data[request][0]/count*100, 3)
        one_request_params['time_perc'] = round(not_render_data[request][1]/time*100,3)
        one_request_params['time_med'] = round(median(not_render_data[request][3]), 3)
        return_data.append(one_request_params)
    # Сортирует список словарей по параметру time_sum.
    sorted_return_data = sorted(return_data, key=lambda x: x['time_sum'], reverse = True)
    # Возвращает первые n отсортированных строк, где n равно
    # параметру report_size в конфиге
    return sorted_return_data[0:(int(report_size)+1)]


def median(sample): 
    """
    функция берет образец числовых значений и возвращает их медиану
    """
    count = len(sample) 
    index = count // 2 
    if count % 2: 
        return sorted(sample)[index] 
    return sum(sorted(sample)[index - 1:index + 1]) / 2 


def render_tpl(data, report_dir, file_name):
    """
    Функция, которая вставляет в шаблон данные, полученные парсингом 
    и "отрендеренные". 
    
    parameters: 
    - data - "отрендеренные данные"
    - report_dir - путь до папки, предназначенной для хранения отчетов
    - file_name - имя файла отчета, который создается данной функцией
    """
    tpl = open('report.html', 'r+').read()
    tpl = tpl.split('$table_json')
    render_tpl = tpl[0]+str(data)+tpl[1]
    ready_f = open(report_dir+'/report-'+file_name+'.html', 'w+')
    ready_f.write(render_tpl)


def read_file(filename, extension):
    """
    Генератор для чтения построчно из файла лога. 

    parameters: 
    - filename - название файла лога, 
    - extension - формат файла лога (для выбора метода открытия файла)
    """
    file = gzip.open(filename,'rb') if extension == 'gz' else open(filename,'rb')
    for row in file:
        yield row.decode()        


def get_last_file(log_dir, logging):
    """
    Функция, предназначенная для выбора "нужного" файла лога для парсинга.
    Выбирает файл, у которого в названии указана самая
    поздняя дата. 

     parameters: 
    - config - конфигурационные настройки, 
    - logging - объект класса, предназначенного для логирования
    """
    try:
        files_name = os.listdir(log_dir)
    except FileNotFoundError:
        logging.error('invalid file path')
        return False
    # Срабатывает, если в папке логов существуют файлы
    if files_name:
        last_file = {}
        last_file['date'] = float('-inf')
        for file_name in files_name:
            # Парсинг названий всех файлов
            date_format = re.findall(r'(\d{8,8}).([gzplain]*)', file_name)
            try:
                # Сравнение даты файла и выбор самой поздней 
                if last_file['date'] < int(date_format[0][0]):
                    last_file['name'] = file_name
                    last_file['date'] = int(date_format[0][0])
                    last_file['format'] = date_format[0][1]
            # Выбрасывает данную ошибку когда один из файлов 
            # не удаось распарсить
            except IndexError:
                pass
        # Еси есть параметра "name",то значит файл для парсинга нашелся.
        # Возвращаем его.
        if 'name' in last_file:
            return (last_file)
        
        logging.error('no one correct file')
        return False
    # Если в папке логов нет - записываем в лог-файл ошибку
    logging.error('folder is empty')
    return False

def isset_report(report_dir, file_date):
    if os.path.exists(report_dir+'/report-'+file_date+'.html'):
        return True
    return False


# Функция для парсинга параметров, переданных через консоль.
def createParser ():
    parser = argparse.ArgumentParser()
    parser.add_argument ('-с', '--config', default='config.ini')
    return parser


if __name__ == "__main__":
    parser = createParser()
    namespace = parser.parse_args(sys.argv[1:])
    main(config, namespace.config)
    
