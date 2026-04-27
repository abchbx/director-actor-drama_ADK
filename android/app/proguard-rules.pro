# D-23-09: 保守 keep 策略 — 只 keep DTO 和接口，其余交给 R8 自动分析

# ===== DTO 层 =====
# 所有 kotlinx.serialization 的 @Serializable 类必须 keep（序列化反射）
-keepattributes *Annotation*, InnerClasses, Signature
-keep class kotlinx.serialization.** { *; }
-keepclassmembers class kotlinx.serialization.** {
    *** Companion;
}
-keepclasseswithmembers class **.data.remote.dto.** {
    <fields>;
}

# ===== API 接口 =====
# Retrofit 接口方法必须 keep
-keep,allowobfuscation interface **.data.remote.api.** {
    *** *(...);
}
-keepclassmembers,allowobfuscation interface **.data.remote.api.** {
    *** *(...);
}

# ===== SceneBubble 密封类 — @SerialName 多态序列化需要类名匹配 =====
-keep class com.drama.app.domain.model.SceneBubble { *; }
-keep class com.drama.app.domain.model.SceneBubble$* { *; }
-keep class com.drama.app.domain.model.InteractionType { *; }

# ===== OkHttp / Retrofit =====
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn retrofit2.**

# ===== Hilt / Dagger =====
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.managers.ViewComponentManager$FragmentContextWrapper { *; }

# ===== Compose =====
-keep class androidx.compose.** { *; }
-dontwarn androidx.compose.**

# ===== Coroutines =====
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# ===== Application 类 =====
-keep class com.drama.app.DramaApplication { *; }
-keep class com.drama.app.di.** { *; }

# ===== OkHttp Interceptors (D-23-10) =====
# Interceptors instantiated by Hilt need their class names preserved
-keep class com.drama.app.data.remote.interceptor.** { *; }

# ===== WebView / JS Bridge (if any) =====
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
