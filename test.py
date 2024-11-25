import unittest
from log_analyzer import *
import logging

class SimplisticTest(unittest.TestCase):

	# Проверка на работоспособность функции получения медианы
	def test_equal_median(self):
		self.failUnlessEqual(median([1, 3, 7, 10, 8, 2]), 5)

	# Проверка на работоспособность функции получения медианы
	def test_not_equal_median(self):
		self.failIfEqual(median([1, 3, 7, 10, 8, 2]), 4)

	# Проверка на возвращение функцией значения "False" ппри неправильно 
	# названной папке с логами (не существует такой папки)
	def test_fail_if_get_last_file_1(self):
		self.failIf(get_last_file('/.false_dir', logging))

	# Проверка на корректное возвращение параметров файла с логами
	def test_equal_get_last_file(self):
		self.failUnlessEqual(get_last_file('test_dir/log', logging), 
							{'date': 20170630, 'name': 'nginx-access-ui.log-20170630.gz', 
							'format': 'gz'})

	# Проверка на возвращение функцией значения "False" отсутствии логов 
	# сервера в папке с логами
	def test_fail_if_get_last_file_2(self):
		self.failIf(get_last_file('test_dir/empty_folder', logging))

	# Проверка на возвращение функцией значения "False" при отсутствии 
	# отчета у лога, уоторый в папке логов имеет самую последнюю дату
	def test_fail_if_isset_report(self):
		self.failIf(isset_report('test_dir/report', '20170708'))

	# Проверка на возвращение функцией значения "False" при неправильно 
	# созданном файле конфига
	def test_fail_if_read_config_1(self):
		config = {
		    "REPORT_SIZE": 100,
		    "REPORT_DIR": "./reports",
		    "LOG_DIR": "./log",
		    "LOG_FILE":"my_super_log.log"
		}
		self.failIf(read_config(config, 'test_dir/false_config.ini', logging))

	# Проверка на возвращение функцией значения "False" при отсутствии 
	# дефолтного конфига
	def test_fail_if_read_config_2(self):
		config = {
		    "REPORT_SIZE": 100,
		    "REPORT_DIR": "./reports",
		    "LOG_DIR": "./log",
		    "LOG_FILE":"my_super_log.log"
		}
		self.failIf(read_config(config, 'test_dir/config.ini', logging))

	# Проверка на возвращение функцией значения "False" при отсутствии 
	# неправильно указанного названия конфига
	def test_fail_if_read_config_2(self):
		config = {
		    "REPORT_SIZE": 100,
		    "REPORT_DIR": "./reports",
		    "LOG_DIR": "./log",
		    "LOG_FILE":"my_super_log.log"
		}
		self.failIf(read_config(config, 'test_dir/no_such_config.ini', logging))

if __name__ == '__main__':
	unittest.main()
