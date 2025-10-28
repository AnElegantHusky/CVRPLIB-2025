import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_multiple_csv_comparison(folder_names, csv_filenames, legend_names, savename):
    """
    Compare curves from multiple CSV files across different folders
    
    Parameters:
    folder_names: list, folder names
    csv_filenames: list, CSV file names to compare
    legend_names: list, legend names for different folders
    """
    
    # Create a figure with subplots for each CSV file
    fig, axes = plt.subplots(1, len(csv_filenames), figsize=(5*len(csv_filenames), 6))
    
    # If only one CSV file, make axes a list for consistent handling
    if len(csv_filenames) == 1:
        axes = [axes]
    
    for csv_idx, csv_file in enumerate(csv_filenames):
        ax = axes[csv_idx]
        
        for folder_idx, folder in enumerate(folder_names):
            # Construct file path
            file_path = os.path.join(folder, csv_file)
            
            try:
                # Read CSV file with semicolon separator
                df = pd.read_csv(file_path, sep=';')
                
                # Assuming first column is time, second is fitness
                time = df.iloc[:, 0]
                fitness = df.iloc[:, 1]
                
                # Plot the data
                ax.plot(time, fitness, label=legend_names[folder_idx], linewidth=2)
                
            except FileNotFoundError:
                print(f"Warning: File {file_path} not found. Skipping.")
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        # Customize each subplot with CSV filename as title
        ax.set_xlabel('Time')
        ax.set_ylabel('Fitness')
        ax.set_title(csv_file)  # Use CSV filename as title
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(savename)
    plt.show()

def plot_separate_csv_comparison(folder_names, csv_filenames, legend_names):
    """
    Create separate plots for each CSV file comparison
    
    Parameters:
    folder_names: list, folder names
    csv_filenames: list, CSV file names to compare
    legend_names: list, legend names for different folders
    """
    
    for csv_idx, csv_file in enumerate(csv_filenames):
        plt.figure(figsize=(10, 6))
        
        for folder_idx, folder in enumerate(folder_names):
            # Construct file path
            file_path = os.path.join(folder, csv_file)
            
            try:
                # Read CSV file with semicolon separator
                df = pd.read_csv(file_path, sep=';')
                
                # Assuming first column is time, second is fitness
                time = df.iloc[:, 0]
                fitness = df.iloc[:, 1]
                
                # Plot the data
                plt.plot(time, fitness, label=legend_names[folder_idx], linewidth=2)
                
            except FileNotFoundError:
                print(f"Warning: File {file_path} not found. Skipping.")
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        # Customize plot with CSV filename as title
        plt.xlabel('Time')
        plt.ylabel('Fitness')
        plt.title(csv_file)  # Use CSV filename as title
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

# Example usage:
if __name__ == "__main__":
    # Define your parameters here
    csv_files = ["XLTEST-n1048-k139.csv", "XLTEST-n2168-k625.csv", "XLTEST-n6034-k1234.csv"]

    '''
    savename = 'dmax_sensitivity'
    folders = ["AILSII_dmax_20", "AILSII_default", "AILSII_dmax_60"]
    legends = ["dmax = 20", "dmax = 30", "dmax = 60"]
    
    savename = 'dmin_sensitivity'
    folders = ["AILSII_dmin_5", "AILSII_default", "AILSII_dmin_25"]
    legends = ["dmin = 5", "dmin = 15", "dmin = 25"]

    savename = 'varphi_sensitivity'
    folders = ["AILSII_varphi_20", "AILSII_default", "AILSII_varphi_80"]
    legends = ["varphi = 20", "varphi = 40", "varphi = 80"]

    savename = 'gamma_sensitivity'
    folders = ["AILSII_gamma_15", "AILSII_default", "AILSII_gamma_60"]
    legends = ["gamma = 15", "gamma = 30", "gamma = 60"]
    '''
    
    savename = 'verify'
    folders = ["AILSII_default", "AILSII_default_verify",]
    legends = ["defalut", "set"]
    # Option 1: All plots in one figure (subplots)
    plot_multiple_csv_comparison(folders, csv_files, legends,savename)
    
    # Option 2: Separate figures for each CSV file
    # plot_separate_csv_comparison(folders, csv_files, legends)
