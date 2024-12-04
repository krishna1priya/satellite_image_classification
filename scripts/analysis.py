import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from torchvision import models, transforms
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from data_loader import SatelliteDataset
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import accuracy_score


# =====================
# Feature Extraction for Traditional ML Models
# =====================
def extract_features(data_dir, img_size=(224, 224)):
    """
    Extract features from images using a pre-trained ResNet model.
    Args:
        data_dir (str): Path to dataset directory.
        img_size (tuple): Image resizing dimensions.
    Returns:
        features (np.array): Extracted feature vectors.
        labels (np.array): Corresponding labels.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    transform = transforms.Compose([
        transforms.Resize(img_size),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # Load dataset
    dataset = SatelliteDataset(data_dir, transform=transform)
    data_loader = torch.utils.data.DataLoader(dataset, batch_size=32, shuffle=False)

    # Load pre-trained ResNet model (feature extractor)
    model = models.resnet18(pretrained=True)
    model = nn.Sequential(*list(model.children())[:-1])  # Removes the final classification layer
    model.to(device)
    model.eval()

    features = []
    labels = []

    # Extract features
    with torch.no_grad():
        for images, lbls in data_loader:
            images = images.to(device)
            output = model(images)
            output = output.view(output.size(0), -1)  # Flatten features
            features.append(output.cpu().numpy())
            labels.extend(lbls.numpy())

    features = np.concatenate(features, axis=0)
    labels = np.array(labels)

    return features, labels

def train_ml_models(features, labels):
    """
    Train traditional ML models and compare their performance.
    Args:
        features (np.array): Extracted feature vectors.
        labels (np.array): Corresponding labels.
    """
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    models = {
        "KNN": KNeighborsClassifier(n_neighbors=5),
        "SVM": SVC(kernel="rbf", probability=True),
        "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=100, random_state=42)
    }

    # Train and evaluate models
    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        print(f"Results for {name}:")
        print(classification_report(y_test, y_pred))

# =====================
# Training ResNet and Custom
# =====================
def get_model(model_name, num_classes):
    """
    Returns the specified model architecture.
    Args:
        model_name (str): Name of the model architecture ('resnet', 'custom').
        num_classes (int): Number of output classes.
    """
    if model_name == "resnet":
        model = models.resnet18(pretrained=True)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
    elif model_name == "custom":
        model = CustomCNN(num_classes)
    else:
        raise ValueError(f"Model {model_name} not supported.")
    return model

class CustomCNN(nn.Module):
    """
    A simple custom CNN for terrain classification.
    """
    def __init__(self, num_classes):
        super(CustomCNN, self).__init__()
        self.conv_layers = nn.Sequential(
            nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )
        self.fc_layers = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 56 * 56, 128),
            nn.ReLU(),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        x = self.conv_layers(x)
        x = self.fc_layers(x)
        return x

def train_model(data_dir, model_name, num_epochs=10, batch_size=32, learning_rate=0.001, num_classes=4):
    """
    Train the specified model.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training {model_name} on {device}")

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    dataset = SatelliteDataset(data_dir, transform=transform)
    train_size = int(0.8 * len(dataset))
    test_size = len(dataset) - train_size
    train_dataset, test_dataset = torch.utils.data.random_split(dataset, [train_size, test_size])

    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    model = get_model(model_name, num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    for epoch in range(num_epochs):
        model.train()
        running_loss = 0.0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        print(f"{model_name} - Epoch [{epoch+1}/{num_epochs}], Loss: {running_loss/len(train_loader):.4f}")

    model_save_path = f"models/{model_name}_terrain_classifier.pth"
    torch.save(model.state_dict(), model_save_path)
    print(f"Model {model_name} saved to {model_save_path}")


def plot_model_performance(models, X_test, y_test, deep_learning_results):
    """
    Visualize accuracy and training time per epoch for ML and deep learning models.
    Args:
        models (dict): Dictionary of trained ML models.
        X_test (np.array): Test feature set for ML models.
        y_test (np.array): Test labels for ML models.
        deep_learning_results (list of dict): Accuracy and training time for DL models.
    """
    # Evaluate traditional ML models
    ml_accuracies = {}
    ml_times = {}
    for name, model_data in models.items():
        model, train_time = model_data
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        ml_accuracies[name] = accuracy
        ml_times[name] = train_time

    # Extract deep learning results
    dl_accuracies = {result['name']: result['accuracy'] for result in deep_learning_results}
    dl_times = {result['name']: result['avg_time_per_epoch'] for result in deep_learning_results}

    # Combine results
    combined_accuracies = {**ml_accuracies, **dl_accuracies}
    combined_times = {**ml_times, **dl_times}

    # Visualization
    fig, ax1 = plt.subplots(figsize=(12, 6))

    color = 'tab:blue'
    ax1.set_xlabel("Models")
    ax1.set_ylabel("Accuracy", color=color)
    ax1.bar(combined_accuracies.keys(), combined_accuracies.values(), color=color, alpha=0.6, label="Accuracy")
    ax1.tick_params(axis='y', labelcolor=color)

    ax2 = ax1.twinx()  # Create a twin y-axis for time
    color = 'tab:orange'
    ax2.set_ylabel("Average Time/Epoch (seconds)", color=color)
    ax2.plot(combined_times.keys(), combined_times.values(), color=color, marker='o', label="Time/Epoch")
    ax2.tick_params(axis='y', labelcolor=color)

    plt.title("Model Performance: Accuracy vs. Training Time/Epoch")
    plt.savefig("analysis")
    fig.tight_layout()
    plt.show()

def train_model_with_time(data_dir, model_name, num_epochs=10, batch_size=32, learning_rate=0.001, num_classes=4):
    """
    Train the specified model and measure training time per epoch.
    Returns:
        dict: Dictionary containing model name, accuracy, and avg training time/epoch.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training {model_name} on {device}")

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    dataset = SatelliteDataset(data_dir, transform=transform)
    train_size = int(0.8 * len(dataset))
    test_size = len(dataset) - train_size
    train_dataset, test_dataset = torch.utils.data.random_split(dataset, [train_size, test_size])

    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    model = get_model(model_name, num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    total_time = 0.0
    for epoch in range(num_epochs):
        model.train()
        epoch_start = time.time()
        running_loss = 0.0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        epoch_time = time.time() - epoch_start
        total_time += epoch_time

        print(f"{model_name} - Epoch [{epoch+1}/{num_epochs}], Loss: {running_loss/len(train_loader):.4f}, Time: {epoch_time:.2f}s")

    avg_time_per_epoch = total_time / num_epochs

    # Evaluate model
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for images, labels in test_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()

    accuracy = correct / total
    print(f"{model_name} - Test Accuracy: {accuracy:.4f}, Avg Time/Epoch: {avg_time_per_epoch:.2f}s")

    return {"name": model_name, "accuracy": accuracy, "avg_time_per_epoch": avg_time_per_epoch}

if __name__ == "__main__":
    data_dir = "../data"

    print("Extracting features using ResNet for traditional ML models...")
    features, labels = extract_features(data_dir)
    print("Features extracted. Training traditional ML models...")

    # Train ML models and record training time
    X_train, X_test, y_train, y_test = train_test_split(features, labels, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    ml_models = {}
    for name, ModelClass in [("KNN", KNeighborsClassifier(n_neighbors=5)),
                             ("SVM", SVC(kernel="rbf", probability=True)),
                             ("Random Forest", RandomForestClassifier(n_estimators=100, random_state=42)),
                             ("Gradient Boosting", GradientBoostingClassifier(n_estimators=100, random_state=42))]:
        start_time = time.time()
        model = ModelClass
        model.fit(X_train, y_train)
        training_time = time.time() - start_time
        ml_models[name] = (model, training_time)

    print("Training deep learning models...")
    deep_learning_results = []
    for model_name in ["resnet", "custom"]:
        dl_result = train_model_with_time(data_dir, model_name)
        deep_learning_results.append(dl_result)

    print("Visualizing model performance...")
    plot_model_performance(ml_models, X_test, y_test, deep_learning_results)