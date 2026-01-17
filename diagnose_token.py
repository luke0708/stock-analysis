#!/usr/bin/env python
"""
Tushare 诊断工具
"""
import sys

def test_token(token):
    """测试 Token 是否有效"""
    print(f"\n{'='*60}")
    print("🔍 Tushare Token 诊断")
    print(f"{'='*60}\n")
    
    # 1. 基本检查
    print("1️⃣ Token 格式检查:")
    if not token:
        print("   ❌ Token 为空")
        return False
    
    if len(token) < 20:
        print(f"   ⚠️ Token 长度过短 ({len(token)} 字符)，正常应该 30+ 字符")
    else:
        print(f"   ✅ Token 长度: {len(token)} 字符")
    
    if ' ' in token:
        print("   ⚠️ Token 中包含空格，请去除")
        token = token.strip()
    
    print(f"   Token 预览: {token[:5]}...{token[-5:]}")
    
    # 2. 导入测试
    print("\n2️⃣ Tushare 库导入测试:")
    try:
        import tushare as ts
        print("   ✅ Tushare 库导入成功")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        print("   请运行: pip install tushare")
        return False
    
    # 3. Token 设置测试
    print("\n3️⃣ Token 设置测试:")
    try:
        ts.set_token(token)
        pro = ts.pro_api()
        print("   ✅ Token 设置成功，API 对象创建成功")
    except Exception as e:
        print(f"   ❌ 设置失败: {e}")
        return False
    
    # 4. API 调用测试
    print("\n4️⃣ API 调用测试:")
    try:
        print("   正在测试获取股票列表...")
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        if df is not None and not df.empty:
            count = len(df)
            print(f"   ✅ API 调用成功！获取到 {count} 只股票")
            print(f"   示例: {df.iloc[0]['name']} ({df.iloc[0]['ts_code']})")
            return True
        else:
            print("   ⚠️ API 返回空数据")
            return False
    except Exception as e:
        print(f"   ❌ API 调用失败: {e}")
        error_msg = str(e).lower()
        if 'token' in error_msg or 'auth' in error_msg:
            print("\n   💡 提示: Token 可能无效或过期")
            print("   请访问 https://tushare.pro 检查：")
            print("   - 账号是否已激活")
            print("   - Token 是否正确复制")
        elif 'network' in error_msg or 'connection' in error_msg:
            print("\n   💡 提示: 网络连接问题")
            print("   请检查网络设置")
        return False
    
    print(f"\n{'='*60}")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = input("请输入您的 Tushare Token: ").strip()
    
    success = test_token(token)
    
    if success:
        print("\n🎉 恭喜！Token 验证成功！")
        print("\n下一步:")
        print("1. 将 Token 添加到 .env 文件:")
        print(f"   echo 'TUSHARE_TOKEN={token}' > .env")
        print("\n2. 或者在终端中设置环境变量:")
        print(f"   export TUSHARE_TOKEN='{token}'")
    else:
        print("\n❌ Token 验证失败")
        print("\n请检查:")
        print("1. 访问 https://tushare.pro 确认账号已激活")
        print("2. 在个人中心复制完整的 Token")
        print("3. 确保 Token 中没有空格或特殊字符")
