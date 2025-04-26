import os
import json
from db_tinydb import backup_data, restore_data, db_users, UserModel

# 检查现有用户
print("查看现有用户:")
users = db_users.all()
for user in users:
    print(f"用户ID: {user['id']}, 用户名: {user['username']}")

if not users:
    print("没有用户存在，无法测试备份和恢复功能")
    exit(1)

# 使用第一个用户进行测试
test_user_id = users[0]['id']
print(f"\n将使用用户ID: {test_user_id} 进行测试")

# 创建测试备份
backup_file = 'test_backup.json'
print(f"\n创建备份文件: {backup_file}")
success = backup_data(test_user_id, backup_file)
print(f"备份创建结果: {'成功' if success else '失败'}")

# 检查文件是否存在
if os.path.exists(backup_file):
    print(f"备份文件存在，大小: {os.path.getsize(backup_file)} bytes")
    
    # 尝试恢复
    print("\n测试恢复功能:")
    restore_success, message = restore_data(test_user_id, backup_file)
    print(f"恢复结果: {message}")
    print(f"状态: {'成功' if restore_success else '失败'}")
else:
    print(f"备份文件创建失败: {backup_file}") 