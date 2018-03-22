# Copyright (c) 2017, MD2K Center of Excellence
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys
import os
import utils.config
import argparse
import traceback
import importlib
from datetime import datetime
from datetime import timedelta

import syslog
from syslog import LOG_ERR
from cerebralcortex.cerebralcortex import CerebralCortex
from cerebralcortex.core.util.spark_helper import get_or_create_sc

cc_config_path = None
metadata_dir = None

def process_features(feature_list, all_users, all_days, is_spark_job=False):
    '''
    This method runs the processing pipeline for each of
    the features in the list.
    '''
    for module in feature_list:
        if is_spark_job:
            spark_context = get_or_create_sc(type="sparkContext")
            rdd = spark_context.parallelize(all_users)
            results = rdd.map(
                lambda user: process_feature_on_user(user, module, all_days, 
                                                     cc_config_path))
            results.count()
            spark_context.stop()
        else:
            for user in all_users:
                process_feature_on_user(user, module, all_days, cc_config_path)

def process_feature_on_user(user, module_name, all_days, cc_config_path):
    try:
        cc = CerebralCortex(cc_config_path)
        module = importlib.import_module(module_name)
        feature_class_name = getattr(module,'feature_class_name')
        feature_class = getattr(module,feature_class_name)
        feature_class_instance = feature_class(cc)
        feature_class_instance.feature_metadata_dir = metadata_dir
        cc.feature_metadata_dir = metadata_dir
        f = feature_class_instance.process
        f(user,all_days)
    except Exception as e:
        err=str(e) + "\n" + str(traceback.format_exc())
        print(err)
        syslog.openlog(ident="CerebralCortex-Driver")
        syslog.syslog(LOG_ERR,err)
        syslog.closelog()

def discover_features(feature_list):
    '''
    This method discovers all the features that are present.
    '''
    feature_dir = os.path.join(utils.config.FEATURES_DIR_NAME)
    found_features = []
    if feature_list:
        feature_subdirs = feature_list
    else:
        feature_subdirs = os.listdir(feature_dir)
    
    for subdir in feature_subdirs:
        feature = os.path.join(feature_dir,subdir)
        if not os.path.exists(feature):
            syslog.openlog(ident="CerebralCortex-Driver")
            syslog.syslog(LOG_ERR,'Feature not found %s.' % subdir)
            syslog.closelog()
            continue
        if os.path.isdir(feature):
            mod_file_path = os.path.join(feature,subdir) + '.py'

            if not os.path.exists(mod_file_path):
                continue
            sys.path.append(feature)
            try:
                module_name = mod_file_path[:-3] # strip '.py'
                module_name_dotted = module_name.replace('/','.')
                found_features.append(module_name_dotted)
                syslog.openlog(ident="CerebralCortex-Driver")
                syslog.syslog('Added feature %s for importing' % feature)
                syslog.closelog()
            except Exception as exp:
                err = str(exp) + '\n' + str(traceback.format_exc())
                print(err)
                syslog.openlog(ident="CerebralCortex-Driver")
                syslog.syslog(LOG_ERR, str(exp) + err)
                syslog.closelog()
    
    return found_features
    

def generate_feature_processing_order(feature_list):
    '''
    This method returns the execution order of processing the features 
    after resolving the inter dependencies.
    '''
    return feature_list


def main():
    global cc_config_path
    global metadata_dir
    # Get the list of the features to process
    parser = argparse.ArgumentParser(description='CerebralCortex '
                                     'Feature Processing Driver')
    parser.add_argument("-f", "--feature-list", help="List of feature names "
                        "seperated by commas", nargs='?', default=None, 
                        required=False)
    parser.add_argument("-c", "--cc-config", help="Path to file containing the "
                        "CerebralCortex configuration", required=True)
    parser.add_argument("-s", "--study-name", help="Study name.", required=True)
    parser.add_argument("-u", "--users", help="Comma separated user uuids", 
                         nargs='?', default=None, required=False)
    parser.add_argument("-sd", "--start-date", help="Start date in " 
                         "YYYYMMDD Format", required=True)
    parser.add_argument("-ed", "--end-date", help="End date in " 
                         "YYYYMMDD Format", required=True)
    parser.add_argument("-m", "--metadata-dir", help="Folder path containing "
                        "the metadata templates for the features." , required=True)
    parser.add_argument("-p", "--spark-job", help="Set to True to enable spark "
                        "parallel execution ", required=False)
    
    args = vars(parser.parse_args())
    feature_list = None
    study_name = None 
    users = None
    start_date = None
    end_date = None
    metadata_dir = None
    date_format = '%Y%m%d'
    is_spark_job = False
    
    if args['feature_list']:
        feature_list = args['feature_list'].split(',')
    if args['cc_config']:
        cc_config_path = args['cc_config']
    if args['study_name']:
        study_name = args['study_name']
    if args['users']:
        users = args['users'].split(',')
    if args['start_date']:
        start_date = datetime.strptime(args['start_date'], date_format)
    if args['end_date']:
        end_date = datetime.strptime(args['end_date'], date_format)
    if args['metadata_dir']:
        metadata_dir = args['metadata_dir']
    if args['spark_job']:
        is_spark_job = args['spark_job']
    
    all_days = []
    while True:
        all_days.append(start_date.strftime('%Y%m%d'))
        start_date += timedelta(days = 1)
        if start_date > end_date : break

    CC = None
    all_users = None
    try:
        CC = CerebralCortex(cc_config_path)
        CC.feature_metadata_dir = metadata_dir
        if not users:
            users = CC.get_all_users(study_name)
            if not users:
                print('No users found')
                return
            if not len(users):
                print('No users found')
                return # no point continuing
            all_users = [usr['identifier'] for usr in users]
        else:
            all_users = users
    except Exception as e:
        print(str(e))
        print( str(traceback.format_exc()))
    if not all_users:
        print('No users found for the study',study_name)
        return

    found_features = discover_features(feature_list)
    feature_to_process = generate_feature_processing_order(found_features)
    process_features(feature_to_process, all_users, all_days, is_spark_job)
    
if __name__ == '__main__':
    main()
