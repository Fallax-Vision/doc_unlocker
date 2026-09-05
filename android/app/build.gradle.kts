plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.fallaxvision.docunlocker"
    compileSdk = 36
    buildToolsVersion = "36.1.0"

    defaultConfig {
        applicationId = "com.fallaxvision.docunlocker"
        minSdk = 26
        targetSdk = 36
        versionCode = 10005
        versionName = "1.0.5"
    }

    signingConfigs {
        create("release") {
            val signingPath = System.getenv("DOC_UNLOCKER_KEYSTORE")
            if (!signingPath.isNullOrBlank()) {
                storeFile = file(signingPath)
                storePassword = System.getenv("DOC_UNLOCKER_STORE_PASSWORD")
                keyAlias = "docunlocker"
                keyPassword = System.getenv("DOC_UNLOCKER_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            isDebuggable = false
            signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

tasks.matching { it.name == "validateSigningRelease" }.configureEach {
    doFirst {
        check(!System.getenv("DOC_UNLOCKER_KEYSTORE").isNullOrBlank()) {
            "Release signing is required. Set DOC_UNLOCKER_KEYSTORE and password environment variables."
        }
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1")
}
