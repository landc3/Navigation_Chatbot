"""
测试数据加载模块
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.utils.data_loader import DataLoader

def test_data_loader():
    """测试数据加载器"""
    print("=" * 50)
    print("测试数据加载模块")
    print("=" * 50)
    
    try:
        # 创建数据加载器
        print("\n1. 创建数据加载器...")
        loader = DataLoader()
        print(f"✅ 成功加载 {len(loader.get_all())} 条数据")
        
        # 测试获取统计信息
        print("\n2. 获取数据统计信息...")
        stats = loader.get_statistics()
        print(f"   总记录数: {stats['total_count']}")
        print(f"   电路图类型数量: {len(stats['diagram_types'])}")
        print(f"   车辆类别数量: {len(stats['vehicle_categories'])}")
        print(f"   品牌数量: {len(stats['brands'])}")
        print(f"   型号数量: {len(stats['models'])}")
        
        # 显示前5个品牌
        print("\n   前5个品牌:")
        sorted_brands = sorted(stats['brands'].items(), key=lambda x: x[1], reverse=True)[:5]
        for brand, count in sorted_brands:
            print(f"     - {brand}: {count}条")
        
        # 测试关键词搜索
        print("\n3. 测试关键词搜索...")
        test_keywords = ["东风", "仪表", "三一", "天龙"]
        for keyword in test_keywords:
            results = loader.search_by_keyword(keyword)
            print(f"   关键词「{keyword}」: 找到 {len(results)} 条结果")
            if results:
                print(f"     示例: {results[0].file_name}")
        
        # 测试根据ID获取
        print("\n4. 测试根据ID获取...")
        diagram = loader.get_by_id(1)
        if diagram:
            print(f"   ID 1: {diagram.file_name}")
            print(f"   层级路径: {' -> '.join(diagram.hierarchy_path)}")
            print(f"   品牌: {diagram.brand}, 型号: {diagram.model}")
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_data_loader()

