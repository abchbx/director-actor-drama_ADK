package com.drama.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.drama.app.ui.components.AppBottomNavigationBar
import com.drama.app.ui.components.bottomNavItems
import com.drama.app.ui.navigation.DramaList
import com.drama.app.ui.navigation.DramaNavHost
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint  // D-09, APP-14
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DramaApp()
        }
    }
}

@Composable
fun DramaApp() {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    // 底部导航仅在 DramaList/DramaCreate/Settings 中显示 (D-11)
    val showBottomBar = bottomNavItems.any { item ->
        currentDestination?.hasRoute(item.route::class) == true
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        bottomBar = {
            if (showBottomBar) {
                AppBottomNavigationBar(navController = navController)
            }
        },
    ) { innerPadding ->
        DramaNavHost(
            navController = navController,
            startDestination = DramaList,  // 暂定 DramaList，Phase 16-02 添加首次启动逻辑
            modifier = Modifier.padding(innerPadding),
        )
    }
}
