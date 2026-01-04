# 文档类别提取模式配置说明

## 概述

为了避免硬编码的品牌、关键词等模式，系统现在支持通过 `category_patterns.json` 配置文件来管理文档类别提取规则。这样当您需要添加新的品牌、关键词或模式时，只需要修改配置文件，无需修改代码。

## 配置文件位置

配置文件位于项目根目录：`category_patterns.json`

## 配置结构说明

### 1. 诊断指导类模式 (`diagnostic_guide`)

用于识别包含诊断指导后缀的文档，例如：`VGT执行器_诊断指导.DOCX`

```json
{
  "diagnostic_guide": {
    "suffixes": ["_诊断指导"]
  }
}
```

**添加新的后缀**：在 `suffixes` 数组中添加新的后缀字符串即可。

### 2. 产品介绍类模式 (`product_intro`)

用于识别产品介绍类文档，例如：`龙擎动力DDI13产品介绍【5】-VGT.DOCX`

```json
{
  "product_intro": {
    "keywords": ["产品介绍"],
    "cleanup_patterns": ["【\\d+】", "[-_]"]
  }
}
```

**添加新的关键词**：在 `keywords` 数组中添加新的关键词。
**添加清理规则**：在 `cleanup_patterns` 数组中添加正则表达式模式。

### 3. 推荐类模式 (`recommended`)

用于识别推荐类文档，例如：`【推荐】解放动力(锡柴)FAW_52E/91E`

```json
{
  "recommended": {
    "prefixes": ["【推荐】"],
    "stop_markers": ["【", "."]
  }
}
```

**添加新的前缀**：在 `prefixes` 数组中添加新的前缀。
**添加停止标记**：在 `stop_markers` 数组中添加提取时应该停止的字符。

### 4. 组件关键词模式 (`component_keywords`)

用于识别包含特定组件的文档，例如：`涡轮增压器转速传感器_诊断指导.DOCX`

```json
{
  "component_keywords": {
    "keywords": ["传感器", "执行器", "增压器"],
    "max_length_after_keyword": 10
  }
}
```

**添加新的组件关键词**：在 `keywords` 数组中添加新的关键词。
**调整提取长度**：修改 `max_length_after_keyword` 值。

### 5. 品牌+系列模式 (`brand_patterns`)

这是最复杂的模式，用于识别品牌和系列信息。

```json
{
  "brand_patterns": {
    "brands": ["解放动力", "龙擎动力", "东风", "重汽", "柳汽", "乘龙"],
    "patterns": [
      {
        "brand": "解放动力",
        "regex": "解放动力[^【]*?(?:FAW[^【]*?|【[^】]*?】)",
        "post_processing": []
      },
      {
        "brand": "柳汽",
        "regex": "柳汽[^_]*?乘龙[^_]*?H\\d+[^_]*?",
        "post_processing": [
          {
            "condition": "contains",
            "value": "乘龙H",
            "regex": "^(.*?乘龙H\\d+[A-Z]?)[_\\s]"
          }
        ]
      }
    ],
    "common_cleanup": ["[-_]\\d+$"]
  }
}
```

**添加新品牌**：
1. 在 `brands` 数组中添加品牌名称
2. 在 `patterns` 数组中添加对应的正则表达式模式配置

**添加新的品牌模式**：
```json
{
  "brand": "新品牌名称",
  "regex": "正则表达式模式",
  "post_processing": [
    {
      "condition": "contains",  // 条件类型
      "value": "需要检查的字符串",  // 条件值
      "regex": "后处理正则表达式"  // 如果条件满足，应用此正则表达式
    }
  ]
}
```

**添加通用清理规则**：在 `common_cleanup` 数组中添加正则表达式模式。

### 6. 通用提取机制 (`fallback`)

当没有匹配到任何特定模式时，使用此机制进行通用提取。

```json
{
  "fallback": {
    "max_length": 30,
    "separators": ["【", "(", "_", "-"],
    "cleanup_patterns": ["[-_]\\d+$", "[-_]诊断指导$"]
  }
}
```

**调整最大长度**：修改 `max_length` 值。
**添加分隔符**：在 `separators` 数组中添加新的分隔符。
**添加清理规则**：在 `cleanup_patterns` 数组中添加正则表达式模式。

### 7. 验证配置 (`validation`)

用于验证和清理提取出的类别名称。

```json
{
  "validation": {
    "min_length": 2,
    "max_length": 50,
    "remove_spaces": true,
    "strip_chars": "【】()（）-_"
  }
}
```

## 使用示例

### 示例1：添加新品牌

假设您需要添加"福田"品牌：

1. 在 `brands` 数组中添加：
```json
"brands": ["解放动力", "龙擎动力", "东风", "重汽", "柳汽", "乘龙", "福田"]
```

2. 在 `patterns` 数组中添加对应的正则表达式：
```json
{
  "brand": "福田",
  "regex": "福田[^_]*?",
  "post_processing": []
}
```

### 示例2：添加新的组件关键词

假设您需要添加"控制器"关键词：

在 `component_keywords.keywords` 数组中添加：
```json
"keywords": ["传感器", "执行器", "增压器", "控制器"]
```

### 示例3：添加新的诊断指导后缀

假设您的文档使用"故障诊断"作为后缀：

在 `diagnostic_guide.suffixes` 数组中添加：
```json
"suffixes": ["_诊断指导", "_故障诊断"]
```

## 配置热重载

配置文件在服务启动时加载。如果需要在不重启服务的情况下更新配置，可以调用：

```python
from backend.app.utils.category_pattern_loader import get_pattern_loader

loader = get_pattern_loader()
loader.reload_config()  # 重新加载配置
```

## 注意事项

1. **正则表达式转义**：在 JSON 中，正则表达式的反斜杠需要转义，例如 `\d` 应该写成 `\\d`
2. **配置文件格式**：确保 JSON 格式正确，否则会使用默认配置
3. **优先级**：模式的匹配顺序是从上到下，第一个匹配的模式会被使用
4. **通用机制**：如果所有特定模式都不匹配，会使用 `fallback` 机制进行通用提取

## 故障排查

如果配置文件无法加载：
- 检查文件路径是否正确
- 检查 JSON 格式是否正确
- 查看控制台输出的警告信息
- 系统会自动使用默认配置作为后备方案

## 向后兼容性

即使配置文件不存在或格式错误，系统也会使用内置的默认配置，确保功能正常运行。

