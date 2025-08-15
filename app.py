import streamlit as st
import dashscope
from dashscope import Generation
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.language_models import BaseChatModel
import time


class QwenChat(BaseChatModel):

    api_key: str

    def _llm_type(self) -> str:
        return "qwen-plus"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # 将 LangChain 消息格式转换为 DashScope 格式
        dashscope_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                dashscope_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                dashscope_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                dashscope_messages.append({"role": "assistant", "content": msg.content})
            else:
                dashscope_messages.append({"role": "user", "content": str(msg)})

        try:
            # 构建并发送API请求
            response = Generation.call(
                model="qwen-plus",
                messages=dashscope_messages,
                temperature=0.3,
                api_key=self.api_key
            )

            # 增加健壮性检查
            if response is None:
                raise Exception("API 调用返回 None。请检查网络连接和API密钥。")

            if response.status_code != 200:
                error_msg = f"API Error ({response.status_code}): {getattr(response, 'message', 'Unknown error')}"
                raise Exception(error_msg)

            output = getattr(response, 'output', None)
            if output is None:
                raise Exception("API 响应缺少 'output' 字段。")

            # 从API响应中提取生成的文本内容
            content = None
            if hasattr(output, 'text') and output.text:
                content = output.text
            elif isinstance(output, dict) and 'choices' in output:
                choices = output.get('choices')
                if choices and isinstance(choices, list) and len(choices) > 0:
                    first_choice = choices[0]
                    if isinstance(first_choice, dict) and 'message' in first_choice:
                        message_dict = first_choice['message']
                        if isinstance(message_dict, dict) and 'content' in message_dict:
                            content = message_dict['content']
            if content is None:
                raise Exception("无法从 API 响应中提取生成的文本内容。")

            # 构造 LangChain 兼容的 ChatResult 对象
            message = AIMessage(content=content)
            generation = ChatGeneration(message=message)
            usage = getattr(response, 'usage', {})
            llm_output = {"token_usage": usage, "model_name": self._llm_type()}
            return ChatResult(generations=[generation], llm_output=llm_output)

        except Exception as e:
            raise Exception(f"调用 Qwen 模型时发生错误: {e}")


# Streamlit应用
st.title("智能项目功能生成器")

# 在侧边栏设置API密钥
api_key = st.sidebar.text_input("输入API密钥", type="password", help="从阿里云DashScope平台获取")

# 项目设置区域 - 添加多模块选择
st.sidebar.header("项目设置")

# 多模块选择 - 显示屏作为固定选项，但用户可以选择是否包含
modules = st.sidebar.multiselect(
    "选择项目模块",
    ["电机", "传感器", "控制器", "通信模块", "执行器", "显示屏"],  # 显示屏作为主要模块添加
    default=["电机", "显示屏"],  # 默认包含传感器和显示屏
    help="选择项目中使用的模块（可多选）"
)

# 确保至少选择了一个模块
if not modules:
    st.sidebar.error("请至少选择一个项目模块")

theme = st.sidebar.text_input("项目主题", "智能流水线", help="例如: 智能灌溉、环境监测、安防系统等")
complexity = st.sidebar.select_slider(
    "项目复杂度",
    options=["简单", "中等", "复杂"],
    value="中等",
    help="选择项目实现的复杂度级别"
)


# 更新提示词模板支持多模块 - 显示屏作为固定模块
def create_prompt(modules, theme, complexity):
    # 生成模块描述字符串
    modules_desc = "、".join(modules)

    motor_note = ""
    if "电机" in modules:
        motor_note = "特别注意：电机模块使用简单转子马达，无需使能控制，仅需通过正反电压即可控制转向。"

    # 固定显示屏描述
    display_note = "项目中包含一个标准显示屏模块，用于显示系统状态和操作信息，不需要分配显示屏的引脚，只需要编写显示屏显示内容。" if "显示屏" in modules else ""

    prompt = f"""
    你是一名嵌入式系统专家，请设计一个基于{modules_desc}的{theme}项目。{display_note}

    **特别注意：**
    1. 系统已经预定义了三个按键：key0、key1、key_up，这些按键不需要在引脚分配表中列出，但必须在功能描述中使用
    2. 显示屏引脚是固定的，不需要在引脚分配表中列出
    3. 所有功能描述中必须使用预定义的三个按键
    4. 电机模块使用简单转子马达，无需使能控制，仅需两个信号线控制电压方向
    5. 所有模块不需要过载保护以及检测装置，不需要检测模块是否正常运行
    6. 所有模块不需要考虑电源，工作电压，以及地线基本因素
    7. 硬件引脚分配不要有任何和显示屏有关的信息
    
    ##### 一、项目信息
    1. **项目标题**: 
        [创建简洁明确的标题]
    2. **主要模块**: 
        {modules_desc}
    3. **复杂度级别**: 
        {complexity}

    ##### 二、核心功能概要
    [用100-150字描述项目整体功能，突出多个模块的协同工作，必须使用key0、key1、key_up按键]

    ##### 三、硬件引脚分配
    | 引脚号 | 功能描述          | 类型    | 关联模块   | 用途说明                  |
    |--------|-------------------|---------|------------|---------------------------|
    | P1     | [模块功能接口]     | 输入    | [模块名称] | [详细说明]               |
    | P2     | [控制信号]         | 输出    | [模块名称] | [详细说明]               |
    | P3     | [通信接口]         | 双向    | [模块名称] | [详细说明]               |
    | ...    | ...               | ...     | ...        | ...                       |

    ##### 四、具体控制要求
    详细描述以下{3 if complexity == "简单" else 5 if complexity == "中等" else 7}个核心功能:

    1. **[功能1名称]**
        - 描述: [详细说明此功能的操作逻辑，必须使用key0、key1、key_up按键]
        - 相关模块: [模块名称]
        - 引脚分配: 
          * [引脚号]: [功能]
          * [引脚号]: [功能]
        - 参数: [参数设定]

    2. **[功能2名称]**
        - 描述: [详细说明此功能的操作逻辑，必须使用key0、key1、key_up按键]
        - 相关模块: [模块名称]
        - 引脚分配: 
          * [引脚号]: [功能]
        - 参数: [参数设定]

    {"3. **[显示功能]**" if "显示屏" in modules else ""}
        {"- 描述: [显示屏的具体功能和使用方法]" if "显示屏" in modules else ""}
        {"- 相关模块: 显示屏" if "显示屏" in modules else ""}
        {"- 显示内容: [说明显示界面内容和格式]" if "显示屏" in modules else ""}

    ... 更多功能（每个功能描述都必须使用key0、key1、key_up按键）

    ##### 五、技术要求
    - 引脚总数: {5 if complexity == "简单" else 8 if complexity == "中等" else 12}个以上
    - 模块协同: {len(modules)}个模块需要协调工作
    {"- 显示屏要求: 需要优化显示内容和刷新速率" if "显示屏" in modules else ""}
    - 按键要求: 必须使用预定义的key0、key1、key_up按键

    请生成专业、完整的项目设计文档，确保：
    1. 不包含显示屏引脚分配
    2. 所有功能描述都使用key0、key1、key_up按键
    """
    return prompt

# 生成项目功能
def generate_project(prompt, api_key):
    if not api_key:
        return "错误: 请先输入API密钥"

    try:
        qwen = QwenChat(api_key=api_key)
        messages = [
            SystemMessage(content="你是一名经验丰富的嵌入式系统工程师，擅长设计多模块硬件系统。"),
            HumanMessage(content=prompt)
        ]
        response = qwen.invoke(messages)
        return response.content
    except Exception as e:
        return f"生成失败: {str(e)}"


# 主界面
st.write("### 项目功能生成器")
st.markdown("选择项目和模块后，点击按钮生成完整设计方案")

if st.button("生成设计方案", type="primary", help="点击生成完整设计文档", disabled=not modules):
    if not api_key:
        st.error("请先输入API密钥")
    elif not modules:
        st.error("请至少选择一个项目模块")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()

        for percent in range(10):
            progress_bar.progress(percent * 10)
            status_text.text(f"准备项目参数... {percent * 10}%")
            time.sleep(0.05)

        prompt = create_prompt(modules, theme, complexity)
        progress_bar.progress(30)
        status_text.text("创建设计方案结构...")

        progress_bar.progress(50)
        status_text.text("正在生成设计方案...")
        project_content = generate_project(prompt, api_key)
        progress_bar.progress(90)

        if project_content.startswith("错误:") or project_content.startswith("生成失败:"):
            status_text.error(project_content)
        else:
            progress_bar.progress(100)
            status_text.success(f"{theme}项目设计方案生成成功！")

            st.subheader(f"{theme}项目设计方案")
            st.markdown(project_content, unsafe_allow_html=True)

        progress_bar.empty()  # 清除进度条
