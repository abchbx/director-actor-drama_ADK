package com.drama.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.toRoute
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
            // Phase 16-02 实现：首次启动连接引导 Dialog
            // 当前占位
        }
        composable<DramaList> {
            DramaListScreen(
                onDramaClick = { dramaId ->
                    navController.navigate(DramaDetail(dramaId))  // D-12
                },
            )
        }
        composable<DramaCreate> {
            DramaCreateScreen()
        }
        composable<Settings> {
            SettingsScreen()
        }
        composable<DramaDetail> { backStackEntry ->
            val args = backStackEntry.toRoute<DramaDetail>()
            DramaDetailScreen(dramaId = args.dramaId)
        }
    }
}
