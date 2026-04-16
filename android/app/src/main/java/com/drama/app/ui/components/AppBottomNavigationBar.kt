package com.drama.app.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavDestination.Companion.hasRoute
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import com.drama.app.ui.navigation.DramaCreate
import com.drama.app.ui.navigation.DramaList
import com.drama.app.ui.navigation.Settings

data class BottomNavItem(
    val label: String,
    val route: Any,
    val icon: @Composable () -> Unit,
)

val bottomNavItems = listOf(
    BottomNavItem(
        label = "戏剧",
        route = DramaList,
        icon = { Icon(Icons.Filled.List, contentDescription = "戏剧列表") },
    ),
    BottomNavItem(
        label = "创建",
        route = DramaCreate,
        icon = { Icon(Icons.Filled.Add, contentDescription = "创建戏剧") },
    ),
    BottomNavItem(
        label = "设置",
        route = Settings,
        icon = { Icon(Icons.Filled.Settings, contentDescription = "设置") },
    ),
)

@Composable
fun AppBottomNavigationBar(
    navController: NavHostController,
    modifier: Modifier = Modifier,
) {
    NavigationBar(modifier = modifier) {
        val currentDestination = navController.currentBackStackEntry?.destination
        bottomNavItems.forEach { item ->
            NavigationBarItem(
                icon = item.icon,
                label = { Text(item.label) },
                selected = currentDestination?.hierarchy?.any {
                    it.hasRoute(item.route::class)
                } == true,
                onClick = {
                    navController.navigate(item.route) {
                        popUpTo(navController.graph.findStartDestination().id) {
                            saveState = true
                        }
                        launchSingleTop = true
                        restoreState = true
                    }
                },
            )
        }
    }
}
