package com.drama.app.ui.screens.dramadetail.orchestrator

import com.drama.app.domain.model.CommandType
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/**
 * CommandRouter 单元测试（per D-23-12, D-23-13）。
 * 覆盖：命令路由、语义判断、显示文本生成。
 */
class CommandRouterTest {

    private lateinit var commandRouter: CommandRouter

    @Before
    fun setup() {
        commandRouter = CommandRouter()
    }

    // ===== route 命令路由 =====

    @Test
    fun `route identifies NEXT command`() {
        assertEquals(CommandType.NEXT, commandRouter.route("/next"))
    }

    @Test
    fun `route identifies ACTION command`() {
        assertEquals(CommandType.ACTION, commandRouter.route("/action something"))
    }

    @Test
    fun `route identifies SPEAK command`() {
        assertEquals(CommandType.SPEAK, commandRouter.route("/speak Alice hello"))
    }

    @Test
    fun `route identifies END command`() {
        assertEquals(CommandType.END, commandRouter.route("/end"))
    }

    @Test
    fun `route identifies STEER command`() {
        assertEquals(CommandType.STEER, commandRouter.route("/steer left"))
    }

    @Test
    fun `route identifies AUTO command`() {
        assertEquals(CommandType.AUTO, commandRouter.route("/auto 3"))
    }

    @Test
    fun `route identifies STORM command`() {
        assertEquals(CommandType.STORM, commandRouter.route("/storm"))
    }

    @Test
    fun `route identifies SAVE command`() {
        assertEquals(CommandType.SAVE, commandRouter.route("/save my_progress"))
    }

    @Test
    fun `route identifies LOAD command`() {
        assertEquals(CommandType.LOAD, commandRouter.route("/load my_progress"))
    }

    @Test
    fun `route identifies LIST command`() {
        assertEquals(CommandType.LIST, commandRouter.route("/list"))
    }

    @Test
    fun `route identifies DELETE command`() {
        assertEquals(CommandType.DELETE, commandRouter.route("/delete my_progress"))
    }

    @Test
    fun `route identifies FREE_TEXT for plain text`() {
        assertEquals(CommandType.FREE_TEXT, commandRouter.route("hello world"))
    }

    @Test
    fun `route identifies FREE_TEXT for text starting with space`() {
        assertEquals(CommandType.FREE_TEXT, commandRouter.route(" /notacommand"))
    }

    // ===== isActionCommand =====

    @Test
    fun `isActionCommand returns true for action types`() {
        assertTrue(commandRouter.isActionCommand(CommandType.ACTION))
        assertTrue(commandRouter.isActionCommand(CommandType.NEXT))
        assertTrue(commandRouter.isActionCommand(CommandType.STEER))
        assertTrue(commandRouter.isActionCommand(CommandType.AUTO))
        assertTrue(commandRouter.isActionCommand(CommandType.STORM))
    }

    @Test
    fun `isActionCommand returns false for non-action types`() {
        assertFalse(commandRouter.isActionCommand(CommandType.SAVE))
        assertFalse(commandRouter.isActionCommand(CommandType.LOAD))
        assertFalse(commandRouter.isActionCommand(CommandType.FREE_TEXT))
        assertFalse(commandRouter.isActionCommand(CommandType.SPEAK))
        assertFalse(commandRouter.isActionCommand(CommandType.END))
    }

    // ===== isPlotChanging =====

    @Test
    fun `isPlotChanging returns true for plot changing types`() {
        assertTrue(commandRouter.isPlotChanging(CommandType.NEXT))
        assertTrue(commandRouter.isPlotChanging(CommandType.ACTION))
        assertTrue(commandRouter.isPlotChanging(CommandType.SPEAK))
        assertTrue(commandRouter.isPlotChanging(CommandType.FREE_TEXT))
        assertTrue(commandRouter.isPlotChanging(CommandType.STEER))
        assertTrue(commandRouter.isPlotChanging(CommandType.AUTO))
        assertTrue(commandRouter.isPlotChanging(CommandType.STORM))
    }

    @Test
    fun `isPlotChanging returns false for non-plot types`() {
        assertFalse(commandRouter.isPlotChanging(CommandType.SAVE))
        assertFalse(commandRouter.isPlotChanging(CommandType.LOAD))
        assertFalse(commandRouter.isPlotChanging(CommandType.LIST))
        assertFalse(commandRouter.isPlotChanging(CommandType.DELETE))
        assertFalse(commandRouter.isPlotChanging(CommandType.END))
    }

    // ===== isLocalCommand =====

    @Test
    fun `isLocalCommand returns true for local types`() {
        assertTrue(commandRouter.isLocalCommand(CommandType.SAVE))
        assertTrue(commandRouter.isLocalCommand(CommandType.LOAD))
        assertTrue(commandRouter.isLocalCommand(CommandType.LIST))
        assertTrue(commandRouter.isLocalCommand(CommandType.DELETE))
    }

    @Test
    fun `isLocalCommand returns false for server commands`() {
        assertFalse(commandRouter.isLocalCommand(CommandType.NEXT))
        assertFalse(commandRouter.isLocalCommand(CommandType.FREE_TEXT))
        assertFalse(commandRouter.isLocalCommand(CommandType.STEER))
        assertFalse(commandRouter.isLocalCommand(CommandType.ACTION))
    }

    // ===== getDisplayText =====

    @Test
    fun `getDisplayText for NEXT`() {
        assertEquals("/next — 推进下一场", commandRouter.getDisplayText("/next", CommandType.NEXT))
    }

    @Test
    fun `getDisplayText for ACTION strips prefix`() {
        assertEquals("attack the dragon", commandRouter.getDisplayText("/action attack the dragon", CommandType.ACTION))
    }

    @Test
    fun `getDisplayText for FREE_TEXT returns original`() {
        assertEquals("hello world", commandRouter.getDisplayText("hello world", CommandType.FREE_TEXT))
    }

    // ===== extractMention =====

    @Test
    fun `extractMention returns actor name for SPEAK command`() {
        assertEquals("Alice", commandRouter.extractMention("/speak Alice hello", CommandType.SPEAK))
    }

    @Test
    fun `extractMention returns null for non-SPEAK command`() {
        assertNull(commandRouter.extractMention("/next", CommandType.NEXT))
    }

    @Test
    fun `extractMention handles missing argument`() {
        assertNull(commandRouter.extractMention("/speak", CommandType.SPEAK))
    }
}
