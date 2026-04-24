package com.drama.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.toRoute
import com.drama.app.ui.screens.connection.ConnectionGuideDialog
import com.drama.app.ui.screens.dramacreate.DramaCreateScreen
import com.drama.app.ui.screens.dramadetail.DramaDetailScreen
import com.drama.app.ui.screens.dramalist.DramaListScreen
import com.drama.app.ui.screens.settings.SettingsScreen

@Composable
fun DramaNavHost(
    navController: NavHostController,
    startDestination: Any,
    modifier: Modifier = Modifier,
) {
    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier,
    ) {
        composable<ConnectionGuide> {
            ConnectionGuideDialog(
                onConnected = {
                    // 导航到 DramaList 并清除 ConnectionGuide 从 back stack (D-15)
                    navController.navigate(DramaList) {
                        popUpTo<ConnectionGuide> { inclusive = true }
                    }
                },
            )
        }
        composable<DramaList> {
            DramaListScreen(
                onDramaClick = { dramaId ->
                    navController.navigate(DramaDetail(dramaId))  // D-12
                },
            )
        }
        composable<DramaCreate> {
            DramaCreateScreen(
                onNavigateToDetail = { dramaId ->
                    // 从创建页进入：skipLoad=true，后端已是当前活跃剧本无需 loadDrama
                    navController.navigate(DramaDetail(dramaId, skipLoad = true)) {
                        popUpTo<DramaList> { inclusive = false }
                        launchSingleTop = true
                    }
                },
            )
        }
        composable<Settings> {
            SettingsScreen()
        }
        composable<DramaDetail> { backStackEntry ->
            val args = backStackEntry.toRoute<DramaDetail>()
            DramaDetailScreen(dramaId = args.dramaId, skipLoad = args.skipLoad)
        }
    }
}
