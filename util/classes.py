#!/usr/bin/python3.6
'''
Created June 6, 2019

@author: Matt Healy
'''
import os, json, pandas as pd, numpy as np, logging, random
from static.static import device_types, device_dict
import splunklib.results as results, splunklib.client as client
from static.credentials import splunk_creds as creds
from util.web_pa import WebpaUtils as web_pa
from util.splunk import query_splunk
from util.confluence import EditConfluence

class Product(object):
	'''
	Common class for all product types

	...
	Attributes
	----------
	__product_type : str
		Product type (RDK-B or RDK-V)
	__email_sender : str
		Email address that the email will be coming from
	__email_subject : str
		Email Subject
	__recipient_list: list
		List of recipients that will receive the email

	Methods
	-------
	get_product_type
		Returns Product type (RDK-B or RDK-V)
	get_email_sender
		Returns email address that the email will be coming from
	get_email_subject
		Returns email subject
	get_recipient_list
		Returns list of recipients that will receive the email
	'''
	def __init__(self, product_type: str):
		'''
		Parameters
		----------
		:param product_type: 
			Product type (RDK-B or RDK-V)
		'''
		self.__product_type = product_type
		self.__email_sender = "MarkerAlert@comcast.com"
		self.__email_subject = f"Missing Mandatory Markers on {product_type}"
		self.__recipient_list = device_dict[product_type]

	def get_product_type(self) -> str:
		'''
		Returns Product Type (RDK-B or RDK-V)
		
		:return __product_type: Product type (RDK-B or RDK-V)
		'''
		return self.__product_type

	def get_email_sender(self) -> str:
		'''
		Returns email address that the email will be coming from

		:return __email_sender: Email address that the email will be coming from
		'''
		return self.__email_sender

	def get_email_subject(self) -> str:
		'''
		Returns email subject

		:return __email_subject: Email subject
		'''
		return self.__email_subject

	def get_recipient_list(self) -> list:
		'''
		Returns list of recipients that will receive the email

		:return __recipient_list: List of recipients that will receive the email
		'''
		return self.__recipient_list


class Device(Product):
	'''
	Class for specific device type (XB3, XB6, XF3, XI5, or XG)

	...
	Attributes
	----------
	__local_macs_path : str
		Absolute path to local list of MACs returned by __splunk_query_macs
	__device_type : str
		Device type (XB3, XB6, XF3, XI5, or XG)
	__splunk_query_macs : str
		Splunk query to return the MACs of the 35 devices that uploaded logs
		most recently
	__splunk_query_daily_percents : str
		Splunk query to return all markers reported in the last 15 mins as well
		as the number of devices that reported them
	__logpath : str
		Absolute path to logfile of interest on device
	__command : str
		DMCLI Command to get device IPv6 from MAC

	Methods
	-------
	get_device_type
		Return Device type (XB3, XB6, XF3, XI5, or XG)
	get_splunk_macs_query
		Return splunk query to return the MACs of the 35 devices that uploaded
		logs most recently
	get_splunk_daily_percents_query
		Return splunk query to return all markers reported in the last 15 mins 
		as well as the number of devices that reported them
	get_logpath
		Return absolute path of important logfile
	get_command
		Return DMCLI Command to get device IP from MAC
	find_online_device
		Depending on Device type, returns mac or ip of online device
	get_conf_error_df
		Return most up-to-date telemetry errors from Confluence for the given 
		device type
	get_configs_difference
		Return np.array of error markers that are present in the most up-to-date
		configs, but are not present on live (field) devices
	write_macs_to_local_file
		Converts list of most-recent macs from ecmMAC to estbMAC and writes 
		to __local_macs_path
	get_macs
		Return the MACs of the 35 devices that uploaded logs most-recently
	get_daily_errors
		Return all markers reported in the last 15 mins as well as the number of
		devices that reported them
	'''

	__local_macs_path = "/home/mhealy066/scripts/TelemetryProject/static/device_addresses/{}.txt"

	def __init__(self, device_type: str):
		'''
		Parameters
		----------
		device_type:
			Device Type (XB3, XB6, XF3, XI5, or XG)
		'''
		self.__device_type = device_type
		super().__init__(device_types[self.__device_type])
		self.__splunk_query_macs = device_dict[self.get_product_type()][
			"devices"][device_type]["splunk_query_macs"]
		self.__splunk_query_daily_percents = device_dict[
			self.get_product_type()]["devices"][device_type][
			"splunk_query_daily_percentages"]
		self.__logpath = device_dict[self.get_product_type()]["devices"][
			device_type]["logpath"]
		self.__command = device_dict[self.get_product_type()]["devices"][
			device_type]["command"]

	def get_device_type(self) -> str:
		'''
		Return Device type (XB3, XB6, XF3, XI5, or XG)
		
		:return __device_type: Device type (XB3, XB6, XF3, XI5, or XG)
		'''
		return self.__device_type

	def get_splunk_macs_query(self) -> str:
		'''
		Return splunk query to return the MACs of the 35 devices that uploaded
		logs most recently
		
		:return __splunk_query_macs: Splunk query to return the MACs of the 35 
			devices that uploaded logs most recently
		'''
		return self.__splunk_query_macs

	def get_splunk_daily_percents_query(self):
		'''
		Return splunk query to return all markers reported in the last 15 mins 
		as well as the number of devices that reported 
		
		:return __splunk_query_daily_percent: Splunk query to return all markers
			reported in the last 15 mins as well as the number of devices that 
			reported them
		'''
		return self.__splunk_query_daily_percent

	def get_logpath(self) -> str:
		'''
		Return absolute path of important logfile
		
		:return __logpath: Absolute path to logfile of interest on device
		'''
		return self.__logpath

	def get_command(self) -> str:
		'''
		Return DMCLI Command for WebPA request
		
		:return __command: DMCLI Command to get device IPv6 from MAC
		'''
		return self.__command

	def find_online_device(self) -> str:
		'''
		Loop through some known MAC addresses (that we have stored locally) of the 
		given device type checking if that router is online. Once we have found one 
		that is online, return that MAC address if the device is of type XI5, 
		else return the IP address. Return None is list of MAC addresses has been
		exhausted without finding online device

		:return ip/mac/False: ecmMAC if device_type="XI5" else IPv6. Return None
			if no device are found to be online
		'''
		found_one = False
		with open(self.__local_macs_path.format(self.get_device_type()), "r") as file:
			macs = file.read().splitlines()
		random.shuffle(macs)

		while found_one == False:

			mac = macs.pop()
			found_one = web_pa.router_is_online(mac)

			logging.info(f'{mac} is {found_one}')
			if found_one:
				if self.get_device_type() == "XI5":
					logging.info(f"MAC for {self.get_device_type()} : {mac}")
					return mac
				elif self.get_device_type() in ["XB3", "XB6", "XF3", "XG"]:
					ip = web_pa.ip_from_mac(mac=mac, device_type=self.get_device_type())
					logging.info(f"IP for {self.get_device_type()} : {ip}")
					return ip

	def get_conf_error_df(self) -> pd.DataFrame:
		'''
		Return most up-to-date telemetry errors from Confluence for the given 
		device type

		:return: df of [ideally] updated markers from Confluence
		'''
		conf = EditConfluence()
		page_id = conf.get_page_id(self.get_device_type())
		return conf.get_page_contents(page_id)

	def get_configs_difference(self) -> np.ndarray:
		'''
		Finds the error markers in the most recent configs that are not present
		in the field devices configs

		:return need_to_be_updated: error markers that are present in 
			the most up-to-date configs, but are not present on live (field) devices
		'''
		file_path = f"{os.getcwd()}/CpeLogs/DOWNLOADED/LIVE/{self.get_device_type()}/{self.get_logpath()}"
		
		def parse_configs(path) -> list:
			"""Removes the heading from the json return by the """
			def __remove_double_quotes(data: str) -> str:
				#some peculiar logic to root cause the issue
				str_data = data.replace("{\"" ,"vikr").replace("\",\"" , "sandep")
				str_data = str_data.replace("\" : \"","arun").replace("\":\"","bindhu")\
					.replace("\"}", "gauth")
				str_data = str_data.replace("\"","")
				return str_data.replace("vikr","{\"" ).replace("sandep","\",\"" )\
					.replace("arun","\"  :  \"").replace("bindhu","\":\"")\
					.replace("gauth","\"}" ).replace("\\","#")

			with open(path, "r",encoding="utf8") as fin:
				content = fin.readlines()
				for i in range(len(content)):
					if "urn:settings:TelemetryProfile" in content[i]:
						data_string = content[i].split('telemetryProfile":' )
						data_string = data_string[1].split(",\"schedule\":\"")
						parse_data = ''

						if self.get_device_type() in ['XB3', 'XB6', 'XF3']:
							parse_data = data_string[0].replace("\"cid\":\"0\"","cid:0")
						elif self.get_device_type() == 'XG' or self.get_device_type() == 'XI5':
							parse_data = __remove_double_quotes(data_string[0])      
						try:
							jsn_data= json.loads(parse_data)
							return jsn_data
						except Exception as e:
							logging.info(e)

		data = parse_configs(file_path)
		errors_configs = list(pd.DataFrame(data)["header"])

		df_conf_errors = self.get_static_error_df()
		errors_conf = list(df_conf_errors["Marker"])

		need_to_be_updated = np.setdiff1d(errors_conf, errors_configs)

		return need_to_be_updated

	def write_macs_to_local_file(self):
		'''
		Converts list of most-recent macs from ecmMAC to estbMAC and writes
		to __local_macs_path
		'''
		macs = [web_pa.ecm_to_estb(mac) for mac in self.get_macs()]

		macs_string = "\n".join(macs)
		with open(self.__local_macs_path.format(self.get_device_type()), "w") as file:
			file.write(macs_string)

	def get_macs(self) -> list:
		'''
		Return the MACs of the 35 devices that uploaded logs most-recently

		:return macs: List of ecmMACs of the 35 devices that uploaded logs
			most-recently
		'''
		service = client.connect(
		    host=creds["host"],
		    port=creds["port"],
		    scheme=creds["scheme"],
		    username=creds["username"],
		    password=creds["password"])

		kwargs_oneshot = {'count': 10000}
		oneshotsearch_results = service.jobs.oneshot(self.get_splunk_macs_query(), **kwargs_oneshot)
		reader = results.ResultsReader(oneshotsearch_results)
		splunk_events = [dict(item) for index, item in enumerate(reader)]
		
		df = pd.DataFrame(splunk_events)
		macs = df["mac"].to_list()
		return macs

	def get_daily_errors(self) -> list:
		'''
		Return all markers reported in the last 15 mins as well as the number of
		devices that reported them

		:return: Error markers that have occurred in the past 15 minutes
		'''
		service = client.connect(
		    host=creds["host"],
		    port=creds["port"],
		    scheme=creds["scheme"],
		    username=creds["username"],
		    password=creds["password"])

		kwargs_oneshot = {'count': 10000}
		oneshotsearch_results = service.jobs.oneshot(self.get_splunk_daily_percents_query(), **kwargs_oneshot)

		reader = results.ResultsReader(oneshotsearch_results)
		splunk_events = [dict(item) for index, item in enumerate(reader)]
		if len(splunk_events) > 0:
			df = pd.DataFrame(splunk_events)
			return df["marker"].to_list()
		else:
			return []
			
