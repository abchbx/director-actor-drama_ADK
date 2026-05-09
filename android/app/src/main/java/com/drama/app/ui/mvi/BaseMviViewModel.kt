package com.drama.app.ui.mvi

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.consumeEach
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * MVI 泛型基类（per D-26-01, D-26-02）。
 *
 * S = State（不可变 UI 状态）
 * I = Intent（用户操作/系统事件密封类）
 * E = Effect（一次性副作用，如导航/Toast/Haptic）
 *
 * 核心机制：
 * 1. [intentQueue] Channel 顺序消费，保证所有 Intent 串行处理，消除并发竞态
 * 2. [reduce] 纯函数，(State, Intent) -> State，无副作用，可独立测试
 * 3. [state] StateFlow 驱动 Compose 重组
 * 4. [effect] SharedFlow 发射一次性事件，UI 层 collect 消费
 */
abstract class BaseMviViewModel<
    S : MviState,
    I : MviIntent,
    E : MviEffect
>(
    initialState: S
) : ViewModel() {

    protected val _state = MutableStateFlow(initialState)
    val state: StateFlow<S> = _state.asStateFlow()

    private val _effect = MutableSharedFlow<E>(extraBufferCapacity = 64)
    val effect: SharedFlow<E> = _effect.asSharedFlow()

    /** Intent 顺序队列 — D-26-01: UNLIMITED 防止 WS 消息突发阻塞 */
    private val intentQueue = Channel<I>(Channel.UNLIMITED)

    init {
        viewModelScope.launch {
            intentQueue.consumeEach { intent ->
                // 串行处理，绝无并发竞态！
                val currentState = _state.value
                val newState = reduce(currentState, intent)
                _state.value = newState
            }
        }
    }

    /** 唯一公共入口 — 所有操作必须经此入队 */
    fun processIntent(intent: I) {
        intentQueue.trySend(intent)
    }

    /** Reducer 纯函数 — 子类实现 (State, Intent) -> State */
    protected abstract fun reduce(state: S, intent: I): S

    /** 发射一次性 Effect */
    protected fun emitEffect(effect: E) {
        _effect.tryEmit(effect)
    }

    override fun onCleared() {
        super.onCleared()
        intentQueue.close()
    }
}
