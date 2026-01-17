#!/bin/bash
# 清理项目冗余文件

echo "🧹 开始清理项目冗余文件..."
echo ""

# 进入项目目录
cd "$(dirname "$0")"

# 创建备份目录
echo "📦 创建备份目录..."
mkdir -p .backup_tests
mkdir -p .backup_old_docs

# 备份测试文件
echo "📋 备份测试文件..."
mv test_data_sources.py .backup_tests/ 2>/dev/null
mv test_enhanced_features.py .backup_tests/ 2>/dev/null
mv test_new_features.py .backup_tests/ 2>/dev/null
mv test_pro_bar.py .backup_tests/ 2>/dev/null
mv test_system.py .backup_tests/ 2>/dev/null
mv test_tushare.py .backup_tests/ 2>/dev/null
mv debug_data.py .backup_tests/ 2>/dev/null
mv diagnose_token.py .backup_tests/ 2>/dev/null
mv update_token.py .backup_tests/ 2>/dev/null
mv run.py .backup_tests/ 2>/dev/null

echo "✅ 测试文件已移动到 .backup_tests/"

# 清理临时文件
echo ""
echo "🗑️  清理临时文件..."
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find . -name ".DS_Store" -delete

echo "✅ 临时文件已清理"

# 显示结果
echo ""
echo "=" * 50
echo "✅ 清理完成！"
echo "=" * 50
echo ""
echo "📊 清理结果："
echo "- 测试文件: 已备份到 .backup_tests/"
echo "- 临时文件: 已删除"
echo ""
echo "💡 提示："
echo "- 备份文件保留在 .backup_tests/ 目录"
echo "- 如需恢复，可从备份目录复制回来"
echo "- 确认无需后可手动删除备份目录"
echo ""
