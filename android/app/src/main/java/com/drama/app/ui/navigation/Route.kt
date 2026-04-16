package com.drama.app.ui.navigation

import kotlinx.serialization.Serializable

// D-15: 导航图路由定义
@Serializable object ConnectionGuide    // 首次引导 (D-14)
@Serializable object DramaList          // 戏剧列表 tab (D-11)
@Serializable object DramaCreate        // 创建 tab (D-11)
@Serializable object Settings           // 设置 tab (D-11)
@Serializable data class DramaDetail(val dramaId: String)  // D-12: 从列表点击进入
