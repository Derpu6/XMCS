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
    ["电机", "传感器", "蜂鸣器", "显示屏", "外部通信"],  # 显示屏作为主要模块添加
    default=["显示屏"],)

# 确保至少选择了一个模块
if not modules:
    st.sidebar.error("请至少选择一个项目模块")

theme = st.sidebar.text_input("项目主题", "智能流水线")

function = st.sidebar.text_area("项目功能", "自动启停", height=100,)

complexity = st.sidebar.select_slider(
    "项目复杂度",
    options=["简单", "中等", "复杂"],
    value="中等",
    help="选择项目实现的复杂度级别"
)


# 更新提示词模板支持多模块 - 显示屏作为固定模块
def create_prompt(modules, theme, function, complexity):
    # 生成模块描述字符串
    modules_desc = "、".join(modules)

    if "电机" in modules:
        motor_note = "特别注意：电机模块使用简单转子马达，无需使能控制，仅需通过正反电压即可控制转向。"
    else:
        motor_note = "特别注意：本项目不包含电机模块"

    if "显示屏" in modules:
        display_note = "特别注意：项目中包含一个标准显示屏模块，用于显示系统状态和操作信息，不需要分配显示屏的引脚，只需要编写显示屏显示内容。"
    else:
        display_note = "特别注意：本项目不包含显示屏模块"

    if "外部通信" in modules:
        communicate_note = "特别注意：外部通信模块只是通过type-c接口使单片机和电脑通信，一般是电脑向单片机发出数字，单片机做出对应的反应。"
    else:
        communicate_note = "特别注意：本项目不包含外部通信模块"

    complexity_note = ""
    if complexity == "简单":
        complexity_note = "基础控制+参数调整+状态显示，无模式切换，key0，key1设计为正常的工作按键，使用简单的的逻辑设计，不使用定时器或外部中断"
    elif complexity == "中等":
        complexity_note = "基础控制+参数调整+多重模式+状态显示+中断处理+安全逻辑，包含1-2个功能切换，如手动模式和自动模式切换，key_up设计为功能切换按键，key0，key1设计为正常的工作按键，使用简单的定时器和外部中断，有较复杂的逻辑"
    else:
        complexity_note = "基础控制+参数调整+多重模式+状态显示+中断处理+安全逻辑，在中等级别基础上增加复杂的逻辑设计以及定时器和外部中断应用"

    prompt = f"""
        你是一位嵌入式系统课程设计出题专家，擅长为电子类专业学生编写标准的单片机控制类项目任务书。请设计一个基于{modules_desc}的{theme}项目，实现以下功能：
        {function}

        {display_note}，{motor_note}，{communicate_note}生成一份格式规范、逻辑严谨、可直接用于教学或竞赛的项目任务书。

        **特别注意：**
        1. 系统已经预定义了三个按键：key0、key1、key_up，两个LED：LED0，LED1，这些按键不需要在引脚分配表中列出，但必须在功能描述中使用
        2. 硬件引脚分配不要有任何和显示屏有关的信息
        3. 所有功能描述中必须使用预定义的三个按键
        4. 电机模块使用简单转子马达，无需使能控制，仅需两个信号线控制电压方向
        5. 所有模块不需要过载保护以及检测装置，不需要检测模块是否正常运行
        6. 所有模块不需要考虑电源，工作电压，以及地线基本因素
        7. 请严格按照以下格式生成内容，使用中文，语言正式、精确，不使用Markdown，不添加额外解释。只输出任务书正文，结构如下：

        ##### 一、项目信息
        1. **项目标题**: 
            一种{theme}控制系统
        2. **主要模块**: 
            {modules_desc}
        3. **复杂度级别**: 
            {complexity}

        ##### 二、核心功能概要
        [用100-150字描述项目整体功能，简要概括系统核心功能，突出所用模块的作用。可分句描述整体流程，突出多个模块的协同工作，必须使用key0、key1、key_up按键]

        ##### 三、硬件引脚分配
        | 引脚号  | 功能描述            | 类型    | 关联模块   | 用途说明                  |
        |--------|-------------------|---------|------------|---------------------------|
        | P1     | [模块功能接口]      | 输入    | [模块名称] | [详细说明]               |
        | P2     | [控制信号]         | 输出    | [模块名称] | [详细说明]               |
        | ...    | ...               | ...     | ...        | ...                       |

        ##### 四、具体控制要求
        {complexity_note}

        1. **[功能1名称]**
            - 描述: [详细说明此功能的操作逻辑，详细描述该功能的控制逻辑、时序、条件判断、模块响应等，使用工程术语，必须使用key0、key1、key_up按键]
            - 相关模块: [模块名称]
            - 引脚分配: 
              * [引脚号]: [功能]
              * [引脚号]: [功能]
            - 参数: [参数设定]

        2. **[功能2名称]**
            - 描述: [详细说明此功能的操作逻辑，详细描述该功能的控制逻辑、时序、条件判断、模块响应等，使用工程术语，必须使用key0、key1、key_up按键]
            - 相关模块: [模块名称]
            - 引脚分配: 
              * [引脚号]: [功能]
            - 参数: [参数设定]

        {"3. **[显示功能]**" if "显示屏" in modules else ""}
            {"- 描述: [显示屏的具体功能和使用方法]" if "显示屏" in modules else ""}
            {"- 相关模块: 显示屏" if "显示屏" in modules else ""}
            {"- 显示内容: [说明显示界面内容和格式]" if "显示屏" in modules else ""}

        ... 更多功能（每个功能描述都必须使用key0、key1、key_up按键）

        请生成专业、完整的项目设计文档，确保：
        1. 硬件引脚分配不要有任何和显示屏有关的信息
        2. 所有功能描述都使用key0、key1、key_up按键,LED0，LED1灯，不准加其他的按键或灯
        3. 硬件引脚分配不要有任何和电源有关的信息
        4. 每个按键功能尽量不要叠加或冲突，不要设计出key0与key1同时控制同一个模块的同一个模式的行为
        5. LED功能尽量不要叠加或冲突，不要设计出两种状态对应一种LED灯行为
        6. 项目要设置一个急停按键，通过外部中断实现，如key1平时是正常的工作按键，当系统开始运行后key1变为急停按键
        """
    return prompt


# 生成项目功能
def generate_project(prompt, api_key):
    if not api_key:
        return "错误: 请先输入API密钥"

    try:
        qwen = QwenChat(api_key=api_key)
        messages = [
            SystemMessage(content="你是一名经验丰富的嵌入式系统工程师，擅长设计多模块硬件教学系统。"),
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

        # 修复这里：添加 function 参数
        prompt = create_prompt(modules, theme, function, complexity)  # 添加 function 参数
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

        progress_bar.empty()
