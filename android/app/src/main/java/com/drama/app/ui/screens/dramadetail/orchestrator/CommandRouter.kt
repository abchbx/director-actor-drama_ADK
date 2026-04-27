package com.drama.app.ui.screens.dramadetail.orchestrator

import com.drama.app.domain.model.CommandType
import javax.inject.Inject

/**
 * 命令路由子组件（per D-23-01, D-23-02）。
 * 处理命令分发、群聊消息、mention 路由。
 * 判断命令类型语义：是否为动作命令、剧情变更命令、本地命令等。
 */
class CommandRouter @Inject constructor() {

    /** 判断命令类型并路由 */
    fun route(text: String): CommandType {
        return CommandType.fromInput(text)
    }

    /** 判断是否为 action 命令（需要 isTyping + isProcessing） */
    fun isActionCommand(commandType: CommandType): Boolean {
        return commandType in listOf(
            CommandType.ACTION, CommandType.NEXT,
            CommandType.STEER, CommandType.AUTO, CommandType.STORM
        )
    }

    /** 判断是否为剧情变更命令 */
    fun isPlotChanging(commandType: CommandType): Boolean {
        return commandType in listOf(
            CommandType.NEXT, CommandType.ACTION, CommandType.SPEAK, CommandType.FREE_TEXT,
            CommandType.STEER, CommandType.AUTO, CommandType.STORM
        )
    }

    /** 判断是否为本地命令（save/load/list/delete） */
    fun isLocalCommand(commandType: CommandType): Boolean {
        return commandType in listOf(CommandType.SAVE, CommandType.LOAD, CommandType.LIST, CommandType.DELETE)
    }

    /** 生成用户气泡的显示文本 */
    fun getDisplayText(text: String, commandType: CommandType): String {
        return when (commandType) {
            CommandType.NEXT -> "/next — 推进下一场"
            CommandType.END -> "/end — 落幕"
            CommandType.ACTION -> text.removePrefix("/action").trim()
            CommandType.SPEAK -> {
                val parts = text.removePrefix("/speak").trim().split(" ", limit = 2)
                if (parts.size >= 2 && parts[0].isNotBlank()) "@${parts[0]} ${parts[1]}" else ""
            }
            CommandType.STEER -> text.removePrefix("/steer").trim()
            CommandType.AUTO -> {
                val numStr = text.removePrefix("/auto").trim()
                numStr.ifBlank { "3" }
            }
            CommandType.STORM -> {
                val focus = text.removePrefix("/storm").trim()
                if (focus.isNotBlank()) "🌪️ 多视角探索：$focus" else "🌪️ 多视角探索"
            }
            CommandType.FREE_TEXT -> text.trim()
            else -> ""  // SAVE, LOAD, LIST, DELETE, CAST — 不显示用户气泡
        }
    }

    /** 生成剧情引导文本 */
    fun getPlotGuidanceText(commandType: CommandType, rawText: String): String {
        return when (commandType) {
            CommandType.NEXT -> "剧情正在转向下一场..."
            CommandType.ACTION -> "剧情已转向：${rawText.removePrefix("/action").trim().take(20)}..."
            CommandType.SPEAK -> "角色正在回应你的指令..."
            CommandType.STEER -> "剧情方向已调整..."
            CommandType.AUTO -> "剧情正在自动推进..."
            CommandType.STORM -> "风暴模式已启动..."
            CommandType.FREE_TEXT -> "剧情正在因你而改变..."
            else -> "剧情已转向..."
        }
    }

    /** 生成剧情引导方向 */
    fun getPlotGuidanceDirection(commandType: CommandType): String {
        return when (commandType) {
            CommandType.NEXT -> "next_scene"
            CommandType.ACTION -> "user_action"
            CommandType.SPEAK -> "actor_speak"
            CommandType.STEER -> "steer"
            CommandType.AUTO -> "auto_advance"
            CommandType.STORM -> "storm"
            else -> "free_text"
        }
    }

    /** 提取 /speak 命令的 mention 目标 */
    fun extractMention(text: String, commandType: CommandType): String? {
        return if (commandType == CommandType.SPEAK) {
            text.removePrefix("/speak").trim().split(" ", limit = 2).getOrNull(0)
        } else null
    }

    /** D-23-04: 主 VM onCleared 时调用 */
    fun cleanup() {
        // CommandRouter 无持久状态，无需特殊清理
    }
}
