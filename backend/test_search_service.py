"""
搜索服务测试脚本
使用keywords.txt中的示例进行测试
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.services.search_service import get_search_service
from backend.app.utils.hierarchy_util import HierarchyUtil


def test_keywords_file():
    """使用keywords.txt中的关键词进行测试"""
    keywords_file = project_root / "keywords.txt"
    
    if not keywords_file.exists():
        print(f"错误：找不到keywords.txt文件: {keywords_file}")
        return
    
    # 读取关键词
    with open(keywords_file, 'r', encoding='utf-8') as f:
        keywords = [line.strip() for line in f if line.strip()]
    
    print(f"从keywords.txt读取了 {len(keywords)} 个测试关键词\n")
    print("=" * 80)
    
    # 获取搜索服务
    search_service = get_search_service()
    
    # 测试每个关键词
    test_results = []
    
    for i, keyword in enumerate(keywords[:10], 1):  # 测试前10个
        print(f"\n测试 {i}/{min(10, len(keywords))}: {keyword}")
        print("-" * 80)
        
        # AND逻辑搜索
        results_and = search_service.search(
            query=keyword,
            logic="AND",
            max_results=5,
            use_fuzzy=True
        )
        
        # OR逻辑搜索
        results_or = search_service.search(
            query=keyword,
            logic="OR",
            max_results=5,
            use_fuzzy=True
        )
        
        print(f"AND逻辑: 找到 {len(results_and)} 个结果")
        print(f"OR逻辑: 找到 {len(results_or)} 个结果")
        
        # 显示AND逻辑的前3个结果
        if results_and:
            print("\nAND逻辑前3个结果:")
            for j, result in enumerate(results_and[:3], 1):
                print(f"  {j}. [ID: {result.diagram.id}] {result.diagram.file_name}")
                print(f"     评分: {result.score:.2f}")
                print(f"     路径: {' -> '.join(result.diagram.hierarchy_path)}")
        elif results_or:
            print("\nOR逻辑前3个结果（AND无结果时）:")
            for j, result in enumerate(results_or[:3], 1):
                print(f"  {j}. [ID: {result.diagram.id}] {result.diagram.file_name}")
                print(f"     评分: {result.score:.2f}")
        
        # 测试选项提取
        if results_or:
            brands = search_service.extract_options(results_or, "brand", max_options=3)
            if brands:
                print(f"\n可用品牌选项: {[b['name'] for b in brands]}")
        
        test_results.append({
            "keyword": keyword,
            "and_count": len(results_and),
            "or_count": len(results_or)
        })
    
    # 统计结果
    print("\n" + "=" * 80)
    print("测试统计:")
    print("=" * 80)
    
    and_total = sum(r["and_count"] for r in test_results)
    or_total = sum(r["or_count"] for r in test_results)
    
    print(f"AND逻辑平均结果数: {and_total / len(test_results):.1f}")
    print(f"OR逻辑平均结果数: {or_total / len(test_results):.1f}")
    
    no_results_and = sum(1 for r in test_results if r["and_count"] == 0)
    no_results_or = sum(1 for r in test_results if r["or_count"] == 0)
    
    print(f"AND逻辑无结果数: {no_results_and}/{len(test_results)}")
    print(f"OR逻辑无结果数: {no_results_or}/{len(test_results)}")


def test_hierarchy_util():
    """测试层级工具功能"""
    print("\n" + "=" * 80)
    print("测试层级工具功能")
    print("=" * 80)
    
    from backend.app.utils.data_loader import get_data_loader
    
    data_loader = get_data_loader()
    all_diagrams = data_loader.get_all()
    
    # 测试品牌筛选
    print("\n1. 测试品牌筛选（东风）:")
    dongfeng_diagrams = HierarchyUtil.filter_by_brand(all_diagrams, "东风")
    print(f"   找到 {len(dongfeng_diagrams)} 个东风相关的电路图")
    if dongfeng_diagrams:
        print(f"   示例: {dongfeng_diagrams[0].file_name}")
    
    # 测试型号筛选
    print("\n2. 测试型号筛选（天龙KL）:")
    tianlong_diagrams = HierarchyUtil.filter_by_model(all_diagrams, "天龙KL")
    print(f"   找到 {len(tianlong_diagrams)} 个天龙KL相关的电路图")
    if tianlong_diagrams:
        print(f"   示例: {tianlong_diagrams[0].file_name}")
    
    # 测试选项提取
    print("\n3. 测试选项提取（品牌）:")
    brand_options = HierarchyUtil.extract_options(all_diagrams, "brand", max_options=10)
    print(f"   前10个品牌:")
    for i, option in enumerate(brand_options[:10], 1):
        print(f"   {i}. {option['name']}: {option['count']} 个")


def test_scoring():
    """测试评分算法"""
    print("\n" + "=" * 80)
    print("测试评分算法")
    print("=" * 80)
    
    search_service = get_search_service()
    
    # 测试完全匹配
    print("\n1. 测试完全匹配:")
    query = "东风天龙KL"
    results = search_service.search(query, logic="AND", max_results=5)
    print(f"   查询: {query}")
    print(f"   找到 {len(results)} 个结果")
    for i, result in enumerate(results[:3], 1):
        print(f"   {i}. [评分: {result.score:.2f}] {result.diagram.file_name}")
    
    # 测试部分匹配
    print("\n2. 测试部分匹配:")
    query = "天龙"
    results = search_service.search(query, logic="OR", max_results=5)
    print(f"   查询: {query}")
    print(f"   找到 {len(results)} 个结果")
    for i, result in enumerate(results[:3], 1):
        print(f"   {i}. [评分: {result.score:.2f}] {result.diagram.file_name}")


if __name__ == "__main__":
    print("=" * 80)
    print("搜索服务测试")
    print("=" * 80)
    
    try:
        # 测试关键词文件
        test_keywords_file()
        
        # 测试层级工具
        test_hierarchy_util()
        
        # 测试评分算法
        test_scoring()
        
        print("\n" + "=" * 80)
        print("测试完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n测试出错: {str(e)}")
        import traceback
        traceback.print_exc()

