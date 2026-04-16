plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.drama.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.drama.app"
        minSdk = 26       // D-10
        targetSdk = 35    // D-10
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }
}

dependencies {
    // Compose BOM
    val composeBom = platform(libs.compose.bom)
    implementation(composeBom)
    androidTestImplementation(composeBom)

    // Compose UI
    implementation(libs.material3)
    implementation(libs.ui)
    implementation(libs.ui.tooling.preview)
    implementation(libs.material.icons.extended)
    debugImplementation(libs.ui.tooling)

    // Core
    implementation(libs.core.ktx)
    implementation(libs.activity.compose)

    // Lifecycle
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.runtime.compose)

    // Navigation Compose (D-08)
    implementation(libs.navigation.compose)

    // Hilt (D-09, APP-14)
    implementation(libs.hilt.android)
    ksp(libs.hilt.android.compiler)
    implementation(libs.hilt.navigation.compose)

    // Network (D-06) — Phase 16-02 使用
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging.interceptor)
    implementation(libs.kotlinx.serialization.json)

    // DataStore (D-04) — Phase 16-02 使用
    implementation(libs.datastore.preferences)

    // Security — EncryptedSharedPreferences for token storage (D-04)
    implementation(libs.security.crypto)
}
