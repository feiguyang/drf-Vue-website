# -*- coding: utf-8 -*-
__author__ = 'HymanLu'

from fabric.api import *
from datetime import datetime
import os
import sys
import re
from reinit_migrations import deleteAllMigrationFiles

env.user = '服务器用户名'
env.password = '对应密码'
env.sudo_user = 'root'
env.sudo_password = 'root用户密码'
env.hosts = ['服务器IP']

_TAR_FILE = 'back-end-and-front-end-src.tar.gz'
_REMOTE_TMP_DIR = '/tmp'
_REMOTE_TMP_TAR = '%s/%s' % (_REMOTE_TMP_DIR, _TAR_FILE)
_REMOTE_BASE_DIR = '/srv/APP_Inventor_case_base_website'
_REMOTE_FRONT_SRC_DIR = _REMOTE_BASE_DIR + '/src/front-end-src'
_REMOTE_BACK_SRC_DIR = _REMOTE_BASE_DIR + '/src/back-end-src'
_LOCAL_CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
_LOCAL_ROOT_DIR = os.path.dirname(_LOCAL_CURRENT_DIR)
_LOCAL_FRONT_SRC_DIR = os.path.join(_LOCAL_ROOT_DIR, 'front-end-src')
_LOCAL_BACK_SRC_DIR = os.path.join(_LOCAL_ROOT_DIR, 'back-end-src')
sys.path.insert(0, os.path.join(os.path.join(os.path.join(os.path.join(_LOCAL_ROOT_DIR, 'back-end-src'), 'tool_scripts'), 'data'), 'setting'))
import local as local_setting, remote as remote_setting
_LOCAL_DB_USER_NAME = local_setting.DATABASES['default']['USER']
_LOCAL_DB_PASSWORD = local_setting.DATABASES['default']['PASSWORD']
_LOCAL_DB_NAME = local_setting.DATABASES['default']['NAME']
_REMOTE_DB_USER_NAME = remote_setting.DATABASES['default']['USER']
_REMOTE_DB_PASSWORD = remote_setting.DATABASES['default']['PASSWORD']
_REMOTE_DB_NAME = remote_setting.DATABASES['default']['NAME']
_BACKUP_TABLES = ['cases_banner', 'cases_cases', 'cases_casescategory', 'users_userprofile', 'questions_answers', 'questions_questions', 'questions_subanswers']

def _now():
    return datetime.now().strftime('%y-%m-%d_%H.%M.%S')

def remoteBackupDB():
    '''
    将       服务器数据库      进行备份（仅对_BACKUP_TABLES中包含的表），然后把备份数据打包下载到本地
    '''
    dt = _now()
    f = 'remote-backup-APP_Inventor_case_base_website-%s.sql' % dt
    with cd(_REMOTE_TMP_DIR):
        cmd_string = 'mysqldump --user=%s --password=%s -t -c --default-character-set=utf8 --quick %s %s > %s' % (_REMOTE_DB_USER_NAME, _REMOTE_DB_PASSWORD, _REMOTE_DB_NAME, ' '.join(_BACKUP_TABLES), f)
        run(cmd_string)
        run('tar -czvf %s.tar.gz %s' % (f, f))
        get('%s.tar.gz' % f, '%s/backup/' % _LOCAL_CURRENT_DIR)
        run('rm -f %s' % f)
        run('rm -f %s.tar.gz' % f)

def localBackupDB():
    '''
    将       本地数据库       进行备份（仅对_BACKUP_TABLES中包含的表）
    '''
    dt = _now()
    f = 'local-backup-APP_Inventor_case_base_website-%s.sql' % dt
    backup_dir = os.path.join(_LOCAL_CURRENT_DIR, 'backup')
    with lcd(backup_dir):
        cmd_string = 'mysqldump --user=%s --password=%s -t -c --default-character-set=utf8 --quick %s %s > %s' % (_LOCAL_DB_USER_NAME, _LOCAL_DB_PASSWORD, _LOCAL_DB_NAME, ' '.join(_BACKUP_TABLES), f)
        local(cmd_string)
        local('tar -czvf %s.tar.gz %s' % (f, f))
        local('rm -f %s' % f)

def _selectBackupFile():
    '''
    选择要进行还原的数据库备份文件
    '''
    backup_dir = os.path.join(_LOCAL_CURRENT_DIR, 'backup')
    fs = os.listdir(backup_dir)
    files = [f for f in fs if f.startswith('remote-backup-') and f.endswith('.sql.tar.gz')]
    files.extend([f for f in fs if f.startswith('local-backup-') and f.endswith('.sql.tar.gz')])
    files.sort()
    if len(files) == 0:
        print('找不到任何备份文件')
        return
    print('一共找到了%s个备份文件:' % len(files))
    print('==================================================')
    n = 0
    for f in files:
        print('%s: %s' % (n, f))
        n = n + 1
    print('==================================================')
    print('')
    try:
        num = int(input('请输入要还原的数据库备份档案: '))
    except ValueError:
        print('非法数字')
        return
    restore_file = files[num]
    yn = input('是否进行还原 %s: %s? y/N ' % (num, restore_file))
    if yn != 'y' and yn != 'Y':
        print('还原操作被取消')
        return
    print('开始进行还原操作...')
    return restore_file

def localRestoreDB():
    '''
    利用数据库备份文件和Django的migration功能对       本地数据库       进行恢复
    '''
    restore_file = _selectBackupFile()
    backup_dir = os.path.join(_LOCAL_CURRENT_DIR, 'backup')
    sqls = [
        'drop database if exists ' + _LOCAL_DB_NAME + ';',
        'create database ' + _LOCAL_DB_NAME + ';',
        # 'grant select, insert, update, delete on awesome.* to \'%s\'@\'localhost\' identified by \'%s\';' % (_LOCAL_DB_USER_NAME, _LOCAL_DB_PASSWORD)
    ]
    for sql in sqls:
        local(r'mysql -u%s -p%s -e "%s"' % (_LOCAL_DB_USER_NAME, _LOCAL_DB_PASSWORD, sql))
    with lcd(backup_dir):
        local('tar zxvf %s' % restore_file)
        deleteAllMigrationFiles()
    with lcd(_LOCAL_BACK_SRC_DIR):
        local('python manage.py makemigrations')
        local('python manage.py migrate')
    with lcd(backup_dir):
        cmd_string = 'mysql -u%s -p%s -f %s < %s' % (_LOCAL_DB_USER_NAME, _LOCAL_DB_PASSWORD, _LOCAL_DB_NAME, restore_file[:-7])
        local(cmd_string)
        print('echo %s' % restore_file[:-7])
        local('rm -f %s' % restore_file[:-7])

def remoteRestoreDB():
    '''
    利用数据库备份文件和Django的migration功能对       服务器数据库      进行恢复
    '''
    restore_file_name = _selectBackupFile()
    sqls = [
        'drop database if exists ' + _REMOTE_DB_NAME + ';',
        'create database ' + _REMOTE_DB_NAME + ';',
        # 'grant select, insert, update, delete on awesome.* to \'%s\'@\'localhost\' identified by \'%s\';' % (_REMOTE_DB_USER_NAME, _REMOTE_DB_PASSWORD)
    ]
    for sql in sqls:
        run(r'mysql -u%s -p%s -e "%s"' % (_REMOTE_DB_USER_NAME, _REMOTE_DB_PASSWORD, sql))
    with lcd(_LOCAL_CURRENT_DIR):
        put('./backup/%s' % restore_file_name, '%s/%s' % (_REMOTE_TMP_DIR, restore_file_name))
    with cd(_REMOTE_BASE_DIR + '/src/operation-and-deployment-src'):
        run('python3 reinit_migrations.py')
    with cd(_REMOTE_BACK_SRC_DIR):
        run('python3 manage.py makemigrations')
        run('python3 manage.py migrate')
    with cd(_REMOTE_TMP_DIR):
        run('tar zxvf %s' % restore_file_name)
        cmd_string = 'mysql -u%s -p%s -f %s < %s' % (_REMOTE_DB_USER_NAME, _REMOTE_DB_PASSWORD, _REMOTE_DB_NAME, restore_file_name[:-7])
        run(cmd_string)
        run('rm -f %s' % restore_file_name[:-7])
        run('rm -f %s' % restore_file_name)

def build():
    '''
    将本地项目代码进行打包，用作备份或者上传服务器进行部署
    '''
    constant_js_file = os.path.join(os.path.join(_LOCAL_FRONT_SRC_DIR, 'src'), 'constants.js')
    original_line_list = open(constant_js_file, 'r').readlines()
    with open(constant_js_file, 'w') as fout:
        for original_line in original_line_list:
            if original_line.startswith('exports.REQUEST_HOST = '):
                fout.write("exports.REQUEST_HOST = 'http://119.23.69.178:8000';\n")
            else:
                fout.write(original_line)
    with lcd(_LOCAL_FRONT_SRC_DIR):
        local('npm run build')
    with open(constant_js_file, 'w') as fout:
        for original_line in original_line_list:
            fout.write(original_line)
    includes = ['back-end-src', 'front-end-src/dist', 'python-lib-requirements.txt', 'operation-and-deployment-src/reinit_migrations.py']
    excludes = ['*__pycache__*', '*.idea*', '*.pyc', 'front-end-src/node_modules']
    local('rm -f dist/%s' % _TAR_FILE)
    with lcd(_LOCAL_ROOT_DIR):
        cmd = ['tar', '--dereference', '-czvf', './operation-and-deployment-src/dist/%s' % _TAR_FILE]
        cmd.extend(['--exclude=%s' % ex for ex in excludes])
        cmd.extend(includes)
        local(' '.join(cmd))

def startServer():
    with cd(_REMOTE_BACK_SRC_DIR):
        run('python3 manage.py runserver 0.0.0.0:8000')

def deploy():
    '''
    将在本地打包好的项目代码上传到服务器然后再解包，然后利用supervisor启动服务，nginx进行请求转发
    '''
    newdir = 'src-%s' % _now()
    run('rm -f %s' % _REMOTE_TMP_TAR)
    with lcd(_LOCAL_CURRENT_DIR):
        put('./dist/%s' % _TAR_FILE, _REMOTE_TMP_TAR)
    with cd(_REMOTE_BASE_DIR):
        run('mkdir %s' % newdir)
    with cd('%s/%s' % (_REMOTE_BASE_DIR, newdir)):
        run('tar -xzvf %s' % _REMOTE_TMP_TAR)
    with cd(_REMOTE_BASE_DIR):
        run('rm -f src')
        run('ln -s %s src' % newdir)
        # run('chown 所有者:组 src')
        # run('chown -R 所有者:组 %s' % newdir)
        run('chmod -R 777 src')
        run('chmod -R 777 %s' % newdir)
    # 在warn_only=True包含的代码快中 如果发生了错误原本是会直接终止的，现在变为不终止了变了警告
    '''
    with settings(warn_only=True):
        sudo('supervisorctl stop APP_Inventor_case_base_website')
        sudo('supervisorctl start APP_Inventor_case_base_website')
        sudo('/etc/init.d/nginx reload')
    '''
    front_end_static_dir = _REMOTE_FRONT_SRC_DIR + '/dist/static'
    back_end_static_dir = _REMOTE_BACK_SRC_DIR + '/static'
    run('mv %s %s' % (front_end_static_dir + '/css/*', back_end_static_dir + '/css'))
    run('mv %s %s' % (front_end_static_dir + '/js/*', back_end_static_dir + '/js'))
    run('mv %s %s' % (_REMOTE_FRONT_SRC_DIR + '/dist/index.html', _REMOTE_BACK_SRC_DIR + '/templates'))
    with cd(_REMOTE_BASE_DIR + '/src'):
        run('pip3 install -r python-lib-requirements.txt')
    with cd(_REMOTE_BACK_SRC_DIR + '/tool_scripts'):
        run('python3 switch_setting.py remote')

RE_FILES = re.compile('\r?\n')

def rollback():
    '''
    项目代码回退到上一个版本，并重启任务
    '''
    with cd(_REMOTE_BASE_DIR):
        r = run('ls -p -1')
        files = [s[:-1] for s in RE_FILES.split(r) if s.startswith('src-') and s.endswith('/')]
        files.sort(cmp=lambda s1, s2: 1 if s1 < s2 else -1)
        r = run('ls -l src')
        ss = r.split(' -> ')
        if len(ss) != 2:
            print('错误: \'src\' 不是一个软链接')
            return
        current = ss[1]
        print('当前版本为: %s\n' % current)
        try:
            index = files.index(current)
        except ValueError as e:
            print('错误: 该软连接非法')
            return
        if len(files) == index + 1:
            print('错误: 不存在上一个版本（当前版本已经是最早备份的了）')
        old = files[index + 1]
        print('==================================================')
        for f in files:
            if f == current:
                print('    当前版本 ---> %s' % current)
            elif f == old:
                print('  准备回退到 ---> %s' % old)
            else:
                print('                   %s' % f)
        print('==================================================')
        print('')
        yn = input('是否继续? y/N ')
        if yn != 'y' and yn != 'Y':
            print('回退操作被取消')
            return
        print('开始回退...')
        sudo('rm -f src')
        sudo('ln -s %s src' % old)
        # sudo('chown 所有者:组 src')
        with settings(warn_only=True):
            sudo('supervisorctl stop awesome')
            sudo('supervisorctl start awesome')
            sudo('/etc/init.d/nginx reload')
        print('回退成功')