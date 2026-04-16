package com.drama.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.drama.app.domain.repository.ServerRepository
import com.drama.app.ui.components.AppBottomNavigationBar
import com.drama.app.ui.components.bottomNavItems
import com.drama.app.ui.navigation.ConnectionGuide
import com.drama.app.ui.navigation.DramaList
import com.drama.app.ui.navigation.DramaNavHost
import com.drama.app.ui.screens.connection.ConnectionViewModel
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint  // D-09, APP-14
class MainActivity : ComponentActivity() {
    @Inject lateinit var serverRepository: ServerRepository

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DramaApp(serverRepository = serverRepository)
        }
    }
}

@Composable
fun DramaApp(serverRepository: ServerRepository) {
    val navController = rememberNavController()

    // D-14/D-15: 首次启动检测 — DataStore 无服务器历史时显示 ConnectionGuide
    val serverConfig by serverRepository.serverConfig
        .collectAsStateWithLifecycle(initialValue = null)
    val startDestination = if (serverConfig == null) ConnectionGuide else DramaList

    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    // 底部导航仅在 DramaList/DramaCreate/Settings 中显示 (D-11)
    val showBottomBar = bottomNavItems.any { item ->
        currentDestination?.hasRoute(item.route::class) == true
    }

    MaterialTheme {  // Phase 16-03 将替换为 DramaTheme
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
                startDestination = startDestination,
                modifier = Modifier.padding(innerPadding),
            )
        }
    }
}
