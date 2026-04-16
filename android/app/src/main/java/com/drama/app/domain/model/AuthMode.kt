package com.drama.app.domain.model

sealed class AuthMode {
    data object Bypass : AuthMode()        // D-02: 无需 token
    data object RequireToken : AuthMode()  // D-02: 需要输入 token
}
