import matplotlib.pyplot as plt

models = ["gemini-pro", "gemini-1.5-flash", "meta-llama-3.1-405b-instruct", "mistrall-small", "codestral-latest"]
query_types = ["simple queries", "complex queries", "curator-written queries"]

results = {
    "gemini-pro": {
        "simple": [5, 0, 46],
        "complex": [11, 0, 39],
        "curator-written": [4, 0, 15]
    },
    "gemini-1.5-flash": {
        "simple": [10, 0, 41],
        "complex": [18, 0, 32],
        "curator-written": [9, 0, 10]
    },
    "meta-llama-3.1-405b-instruct": {
        "simple": [12, 0, 39],
        "complex": [9, 0, 41],
        "curator-written": [4, 0, 15]
    },
    "mistrall-small": {
        "simple": [22, 0, 29],
        "complex": [21, 0, 29],
        "curator-written": [12, 0, 7]
    },
    "codestral-latest": {
        "simple": [14, 0, 37],
        "complex": [7, 0, 43],
        "curator-written": [6, 0, 13]
    }
}

total_queries = {
    "simple": 51,
    "complex": 50,
    "curator-written": 19
}

fig, axs = plt.subplots(nrows=3, ncols=5, figsize=(15, 10), sharex='col',
                        gridspec_kw={'hspace': 0.5, 'wspace': 0.3})

categories = ['NULL', 'Correct Result']
colors = ['orange', 'blue']

for i, query_type in enumerate(query_types):
    query_key = query_type.split()[0].lower()
    for j, model in enumerate(models):
        data = results[model][query_key]
        total = total_queries[query_key]  # Total queries for the current type
        
        # Include only "NULL" and "Correct Result"
        filtered_data = [data[0], data[2]]  # Exclude ERROR
        percentages = [(value / total) * 100 for value in filtered_data]  # Convert to percentages
        
        bars = axs[i, j].bar(categories, percentages, color=colors, edgecolor='black')

        axs[i, j].grid(True, which='both', linestyle='--', linewidth=0.5, color='grey', axis='both')
        for spine in ['top', 'right', 'bottom', 'left']:
            axs[i, j].spines[spine].set_linewidth(1)
            axs[i, j].spines[spine].set_color('black')

        # Ensure y-axis values are percentages
        axs[i, j].set_yticks(range(0, 101, 20))  # From 0% to 100% in steps of 20
        axs[i, j].tick_params(axis='y', labelsize=8)

        # Make x-axis labels visible on all plots
        axs[i, j].tick_params(labelbottom=True, labelsize=8)

        axs[i, j].set_ylim(0, 100)  # Set y-limit to 100% for percentage display

        if i == 0:
            axs[i, j].set_title(model, fontsize=8, fontweight='bold', pad=10)

        if j == 0:
            axs[i, j].set_ylabel(query_type, fontsize=8, fontweight='bold', labelpad=10)

        # Annotating exact ratios above bars
        for bar, value, actual in zip(bars, percentages, filtered_data):
            axs[i, j].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                           f'{actual}/{total}', ha='center', va='bottom', fontsize=8)

plt.subplots_adjust(left=0.07, right=0.97, top=0.92, bottom=0.08)
fig.suptitle('Model Performance Analysis', fontsize=14, fontweight='bold')
plt.show()