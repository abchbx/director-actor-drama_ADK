package com.drama.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint  // D-09, APP-14
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            // DramaApp composable 在 Task 2 中定义
            // 此处暂用占位，Task 2 完成后替换为 DramaApp()
            androidx.compose.material3.Text("DramaApp Loading...")
        }
    }
}
