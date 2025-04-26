import os
import datetime
import json
import shutil
import logging
from db_tinydb import db_users, db_notes, db_categories, db_tags, db_note_tags, db_versions, db_history
from db_tinydb import UserModel, NoteModel, CategoryModel, backup_data

# 配置日志
logging.basicConfig(
    filename='auto_backup.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('auto_backup')

def create_auto_backup():
    """创建系统自动备份"""
    try:
        logger.info("开始创建自动备份")
        
        # 获取所有用户
        users = db_users.all()
        logger.info(f"找到 {len(users)} 个用户")
        
        # 创建备份目录
        backup_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
        if not os.path.exists(backup_root):
            os.makedirs(backup_root)
        
        # 为每个用户创建备份
        for user in users:
            user_id = user['id']
            username = user['username']
            
            # 创建用户备份目录
            user_backup_dir = os.path.join(backup_root, user_id)
            if not os.path.exists(user_backup_dir):
                os.makedirs(user_backup_dir)
                
            # 最多保留5个备份
            max_backups = 5
            
            # 获取现有备份并排序
            existing_backups = []
            for filename in os.listdir(user_backup_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(user_backup_dir, filename)
                    file_time = os.path.getmtime(file_path)
                    existing_backups.append((file_path, file_time))
            
            # 按时间排序（最早的在前）
            existing_backups.sort(key=lambda x: x[1])
            
            # 如果超过最大备份数，删除最老的
            while len(existing_backups) >= max_backups:
                oldest_backup = existing_backups.pop(0)
                logger.info(f"删除旧备份: {oldest_backup[0]}")
                os.remove(oldest_backup[0])
            
            # 创建新备份
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"auto_backup_{timestamp}.json"
            backup_path = os.path.join(user_backup_dir, backup_filename)
            
            # 执行备份
            backup_data(user_id, backup_path)
            logger.info(f"为用户 {username} 创建了备份: {backup_filename}")
            
            # 创建备份信息文件
            info_file = os.path.join(user_backup_dir, 'backup_info.json')
            backup_info = {
                'latest_backup': backup_filename,
                'backup_time': datetime.datetime.now().isoformat(),
                'username': username,
                'user_id': user_id
            }
            
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=4)
            
        logger.info("自动备份完成")
        return True
    except Exception as e:
        logger.error(f"备份过程中发生错误: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    create_auto_backup() 